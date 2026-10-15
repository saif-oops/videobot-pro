"""Video downloader using yt-dlp with Terabox + DiskWala support."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Callable, Optional
import uuid

from bs4 import BeautifulSoup
import httpx
import yt_dlp

from config import DOWNLOAD_DIR, TERABOX_DOMAINS, DISKWALA_DOMAINS

logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def cleanup_orphaned_downloads(download_dir: str = DOWNLOAD_DIR, max_age_seconds: int = 1800) -> int:
    """Clean up leftover temporary download files from previous crashes or sessions."""
    if not os.path.isdir(download_dir):
        return 0
    removed_count = 0
    now = time.time()
    for fname in os.listdir(download_dir):
        fpath = os.path.join(download_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            mtime = os.path.getmtime(fpath)
            is_temp_ext = fname.endswith((".part", ".ytdl", ".temp", ".tmp", ".mp4", ".mkv", ".webm"))
            is_expired = (now - mtime > max_age_seconds) if max_age_seconds > 0 else True
            if is_temp_ext and is_expired:
                os.remove(fpath)
                removed_count += 1
                logger.info(f"Cleaned up orphaned download file: {fname}")
        except Exception as e:
            logger.warning(f"Failed to remove orphaned file {fname}: {e}")
    return removed_count

# ─── URL Helpers ─────────────────────────────────────────────

def detect_platform(url: str) -> Optional[str]:
    """Returns 'terabox', 'diskwala', or None."""
    url_lower = url.lower()
    if any(d in url_lower for d in TERABOX_DOMAINS) or "terabox" in url_lower or "terashare" in url_lower or "1024tera" in url_lower:
        return "terabox"
    if any(d in url_lower for d in DISKWALA_DOMAINS) or "diskwala" in url_lower:
        return "diskwala"
    return None


def extract_url(text: str) -> Optional[str]:
    """Extract first URL from a message."""
    pattern = r'https?://[^\s]+'
    match = re.search(pattern, text)
    return match.group(0) if match else None


# ─── yt-dlp helpers ──────────────────────────────────────────

def _format_size(size_bytes: Optional[int]) -> str:
    if not size_bytes:
        return "Unknown"
    if size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    return f"{size_bytes / (1024 ** 3):.2f} GB"


def _format_duration(secs: Optional[int]) -> str:
    if not secs:
        return "Unknown"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def get_canonical_file_key(url: str) -> str:
    """Normalize TeraBox / DiskWala URLs to a unique persistent key for instant cache lookup."""
    if not url:
        return ""
    # 1. TeraBox surl / share key (matches across all domain variants)
    m = re.search(r'surl=([a-zA-Z0-9_\-]+)', url)
    if not m:
        m = re.search(r'/s/(?:1)?([a-zA-Z0-9_\-]+)', url)
    if m:
        surl = m.group(1).lstrip("1")
        return f"tb:{surl.lower()}"

    # 2. DiskWala file key
    dm = re.search(r'/(?:app|c)/([a-zA-Z0-9]+)', url)
    if dm:
        return f"dw:{dm.group(1).lower()}"

    # 3. Fallback: normalized URL without query tracking params
    clean_url = url.split("?")[0].rstrip("/").lower()
    return f"url:{hashlib.md5(clean_url.encode()).hexdigest()}"


YTDLP_BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    },
}


# ─── TeraBox Extractor ────────────────────────────────────────

def _get_chrome_path() -> Optional[str]:
    """Locate Chrome or Chromium executable cross-platform (Windows / Linux / macOS / Docker)."""
    # 1. Environment variable override
    env_bin = os.getenv("CHROME_BIN") or os.getenv("GOOGLE_CHROME_BIN")
    if env_bin and os.path.exists(env_bin):
        return env_bin

    # 2. Cross-platform PATH lookup via shutil.which
    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        which_path = shutil.which(name)
        if which_path:
            return which_path

    # 3. Known standard Windows installation paths
    for p in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]:
        if p and os.path.exists(p):
            return p

    # 4. Known standard Linux/macOS paths
    for p in [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]:
        if os.path.exists(p):
            return p

    return None


def _extract_terabox_fast(url: str) -> dict:
    """High-speed TeraBox extractor using direct signed stream API. Resolves in < 1 second."""
    import hashlib
    t = int(time.time())
    secret = f"T9do@SM1?xGn5{t}/api/stream.php"
    token = hashlib.md5(secret.encode()).hexdigest()
    api_url = f"https://playterabox.com/api/fetch-video?token={token}&t={t}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Referer": "https://playterabox.com/tools/terabox-online-player",
        "Origin": "https://playterabox.com",
    }
    with httpx.Client(headers=headers, timeout=12.0) as client:
        r = client.post(api_url, json={"url": url})
        if r.status_code == 200:
            data = r.json()
            if data.get("errno") == -4 or "deleted" in str(data).lower():
                raise RuntimeError("⚠️ This TeraBox link has expired or was deleted by the uploader.")
            if data.get("status") == "success" and data.get("list"):
                item = data["list"][0]
                raw_title = item.get("server_filename") or item.get("name") or data.get("title") or "TeraBox Video"
                title = re.sub(r'^[/\\]+', '', raw_title).strip()
                size = int(item.get("size") or data.get("total_size_bytes") or 0)
                duration = int(item.get("duration") or 0)

                stream_url = (
                    item.get("fast_download_link")
                    or item.get("download_link")
                    or item.get("direct_link")
                    or item.get("stream_url")
                )
                m3u8_url = item.get("m3u8_url")
                fast_stream = item.get("fast_stream_url") or {}
                if isinstance(fast_stream, dict) and fast_stream.get("HD"):
                    m3u8_url = fast_stream["HD"]

                thumb = (
                    item.get("thumbnail")
                    or (item.get("thumbs") or {}).get("url3")
                    or (item.get("thumbs") or {}).get("url1")
                )

                fsize_str = item.get("size_formatted") or item.get("formatted_size") or _format_size(size)

                return {
                    "title": title[:80],
                    "thumbnail": thumb,
                    "duration": f"{duration // 60:02d}:{duration % 60:02d}" if duration else "Unknown",
                    "duration_secs": duration,
                    "filesize_str": fsize_str,
                    "formats": [{
                        "format_id": "best",
                        "label": "Original Quality (HD)",
                        "height": 720,
                        "filesize": size,
                        "filesize_str": fsize_str,
                        "ext": "mp4",
                        "direct_url": stream_url,
                        "url": stream_url,
                        "m3u8_url": m3u8_url,
                    }],
                    "platform": "terabox",
                    "url": url,
                    "final_url": url,
                    "stream_url": stream_url,
                    "direct_url": stream_url,
                    "m3u8_url": m3u8_url,
                }
        else:
            try:
                err_data = r.json()
                err_str = str(err_data).lower()
                if "unable to process request" in err_str or "errno\":-1" in err_str or "404" in err_str or "deleted" in err_str:
                    raise RuntimeError("⚠️ This TeraBox link is invalid, expired, or was deleted by the owner.")
            except RuntimeError:
                raise
            except Exception:
                pass
    raise RuntimeError("Primary extractor did not return video data.")


def _extract_terabox_sync(url: str) -> dict:
    """Extract TeraBox video metadata and streaming link. Tries high-speed API first, then falls back."""
    # 1. Try high-speed API (instant, no headless browser needed)
    try:
        return _extract_terabox_fast(url)
    except RuntimeError as re_err:
        if "expired" in str(re_err) or "deleted" in str(re_err):
            raise
    except Exception:
        pass

    # 2. Fallback: Parse via TeraBox share API and headless Chrome
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    final_url = url
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10.0) as client:
            r = client.get(url)
            final_url = str(r.url)
    except Exception:
        final_url = url

    m = re.search(r'surl=([a-zA-Z0-9_\-]+)', final_url)
    if not m:
        m = re.search(r'/s/(?:1)?([a-zA-Z0-9_\-]+)', final_url)
    surl = m.group(1) if m else ""
    if surl.startswith("1") and len(surl) > 20:
        surl = surl[1:]

    m_domain = re.search(r'https?://([^/]+)', final_url)
    domain = m_domain.group(1) if m_domain else "www.1024tera.com"

    meta = {}
    if surl:
        try:
            with httpx.Client(headers=headers, follow_redirects=True, timeout=10.0) as client:
                api_url = f"https://www.1024tera.com/share/list?app_id=250528&shorturl={surl}&root=1"
                r = client.get(api_url)
                if r.status_code == 200:
                    d = r.json()
                    if d.get("errno") == -4:
                        raise RuntimeError("⚠️ This TeraBox link has expired or was deleted by the uploader.")
                    if d.get("errno") == 0 and d.get("list"):
                        items = d["list"]
                        item = next((it for it in items if it.get("category") == "1" or any(it.get("server_filename", "").lower().endswith(ext) for ext in (".mp4", ".mkv", ".mov", ".avi", ".webm"))), items[0])
                        meta = {
                            "title": item.get("server_filename") or "TeraBox Video",
                            "size": int(item.get("size") or 0),
                            "duration": int(item.get("duration") or 0),
                            "thumbnail": (item.get("thumbs") or {}).get("url3") or (item.get("thumbs") or {}).get("url1"),
                        }
        except RuntimeError:
            raise
        except Exception:
            pass

    chrome_bin = _get_chrome_path()
    soup = None
    if chrome_bin:
        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-extensions",
            "--blink-settings=imagesEnabled=false",
            "--dump-dom",
            final_url,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=15)
            soup = BeautifulSoup(res.stdout, "html.parser")
        except Exception as e:
            logger.debug(f"Headless Chrome DOM extraction failed: {e}")
            soup = None

    if soup:
        page_text = soup.get_text()
        if "content has been deleted" in page_text or "expired" in page_text:
            raise RuntimeError("⚠️ This TeraBox link has expired or was deleted by the uploader.")

        video = soup.find("video")
        src = None
        if video and video.get("src"):
            src = video.get("src")
        else:
            source = soup.find("source")
            if source and source.get("src"):
                src = source.get("src")

        if src:
            stream_url = f"https://{domain}{src}" if src.startswith("/") else src
            title = meta.get("title") or (soup.title.string if soup.title else "TeraBox Video")
            title = re.sub(r' - Share Files.*', '', title).strip()
            title = re.sub(r' - TeraBox.*', '', title).strip()
            size = meta.get("size") or 0
            duration = meta.get("duration") or 0
            thumb = meta.get("thumbnail")

            return {
                "title": title[:80],
                "thumbnail": thumb,
                "duration": f"{duration // 60:02d}:{duration % 60:02d}" if duration else "Unknown",
                "duration_secs": duration,
                "filesize_str": _format_size(size),
                "formats": [{
                    "format_id": "best",
                    "label": "Original Quality",
                    "height": 480,
                    "filesize": size,
                    "filesize_str": _format_size(size),
                    "ext": "mp4",
                    "direct_url": stream_url,
                    "url": stream_url,
                }],
                "platform": "terabox",
                "url": url,
                "final_url": final_url,
                "stream_url": stream_url,
                "direct_url": stream_url,
            }

    if meta.get("title"):
        size = meta.get("size") or 0
        return {
            "title": meta["title"][:80],
            "thumbnail": meta.get("thumbnail"),
            "duration": f"{meta['duration'] // 60:02d}:{meta['duration'] % 60:02d}" if meta.get("duration") else "Unknown",
            "duration_secs": meta.get("duration") or 0,
            "filesize_str": _format_size(size),
            "formats": [{
                "format_id": "best",
                "label": "Original Quality",
                "height": 480,
                "filesize": size,
                "filesize_str": _format_size(size),
                "ext": "mp4",
                "direct_url": url,
                "url": url,
            }],
            "platform": "terabox",
            "url": url,
            "final_url": final_url,
            "stream_url": url,
            "direct_url": url,
        }

    raise RuntimeError("❌ Could not extract video stream. Make sure the link is valid and has not expired.")


# ─── Video Info ──────────────────────────────────────────────

async def get_video_info(url: str) -> dict:
    """Fetch metadata without downloading. Returns info dict."""
    platform = detect_platform(url)

    if platform == "terabox":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: _extract_terabox_sync(url))

    if platform == "diskwala":
        return await _diskwala_info(url)

    opts = {**YTDLP_BASE_OPTS, "skip_download": True}

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"Cannot fetch video info: {e}") from e

    # Collect available video+audio formats
    formats: list[dict] = []
    seen: set[int] = set()

    for f in info.get("formats") or []:
        h = f.get("height") or 0
        if f.get("vcodec", "none") == "none" or h == 0:
            continue
        if h in seen:
            continue
        seen.add(h)
        fsize = f.get("filesize") or f.get("filesize_approx") or 0
        formats.append({
            "format_id": f["format_id"],
            "label": f"{h}p",
            "height": h,
            "filesize": fsize,
            "filesize_str": _format_size(fsize),
            "ext": f.get("ext", "mp4"),
        })

    formats.sort(key=lambda x: x["height"], reverse=True)

    # Best overall format as fallback
    if not formats:
        fsize = info.get("filesize") or info.get("filesize_approx") or 0
        formats.append({
            "format_id": "best",
            "label": "Best",
            "height": 0,
            "filesize": fsize,
            "filesize_str": _format_size(fsize),
            "ext": info.get("ext", "mp4"),
        })

    return {
        "title": (info.get("title") or "Video")[:80],
        "thumbnail": info.get("thumbnail"),
        "duration": _format_duration(info.get("duration")),
        "duration_secs": info.get("duration"),
        "formats": formats[:6],
        "filesize_str": _format_size(info.get("filesize") or info.get("filesize_approx")),
        "platform": detect_platform(url) or "unknown",
        "url": url,
        "file_key": get_canonical_file_key(url),
    }


# ─── DiskWala Fallback Scraper ────────────────────────────────

async def _diskwala_info(url: str) -> dict:
    """DiskWala uses client-side device encryption and requires their official mobile app to stream or download."""
    file_id_m = re.search(r'/(?:app|c)/([a-zA-Z0-9]+)', url)
    file_id = file_id_m.group(1) if file_id_m else "file"

    return {
        "title": f"DiskWala Video ({file_id})",
        "thumbnail": None,
        "duration": "V-Player / App",
        "duration_secs": None,
        "formats": [{
            "format_id": "__app__",
            "label": "Stream in V-Player / App",
            "height": 720,
            "filesize": 0,
            "filesize_str": "Cloud Stream",
            "ext": "mp4",
            "direct_url": url,
            "url": url,
        }],
        "filesize_str": "Cloud Stream",
        "platform": "diskwala",
        "url": url,
        "file_id": file_id,
        "is_app_only": True,
        "app_url": url,
    }


# ─── Video Download ───────────────────────────────────────────

class ProgressTracker:
    """Wraps yt-dlp progress hook into an async callback."""

    def __init__(self, callback: Callable[[int, int], None]):
        self.callback = callback
        self._last_call = 0.0
        self._loop = asyncio.get_event_loop()

    def hook(self, d: dict):
        if d["status"] != "downloading":
            return
        now = time.monotonic()
        if now - self._last_call < 3.0:
            return
        self._last_call = now

        downloaded = d.get("downloaded_bytes", 0) or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0

        # Schedule coroutine on the event loop (hook runs in executor thread)
        asyncio.run_coroutine_threadsafe(
            self._async_cb(downloaded, total), self._loop
        )

    async def _async_cb(self, downloaded: int, total: int):
        await self.callback(downloaded, total)


async def download_video(
    url: str,
    format_id: str,
    progress_cb: Optional[Callable] = None,
    direct_url: Optional[str] = None,
) -> str:
    """Download video and return local file path."""

    # Generate a unique, short, Windows-safe filename to avoid Windows MAX_PATH and query string errors
    file_id = f"vid_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    output_tmpl = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    # If direct_url is a plain file (not M3U8 stream), download directly:
    if direct_url and not any(k in direct_url for k in ("m3u8", "share/streaming", "streaming?", "netdisk-video")):
        return await _download_direct(direct_url, progress_cb)

    target_url = direct_url if direct_url else url

    tracker = ProgressTracker(progress_cb) if progress_cb else None
    opts = {
        **YTDLP_BASE_OPTS,
        "outtmpl": output_tmpl,
        "merge_output_format": "mp4",
    }
    if format_id not in ("__direct__", "best"):
        opts["format"] = format_id

    if tracker:
        opts["progress_hooks"] = [tracker.hook]

    loop = asyncio.get_event_loop()

    def _dl():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target_url, download=True)
            return ydl.prepare_filename(info)

    filepath = await loop.run_in_executor(None, _dl)

    # yt-dlp may change extension to mp4 after merge
    if not os.path.exists(filepath):
        base = os.path.splitext(filepath)[0]
        for ext in ("mp4", "mkv", "webm", "ts"):
            candidate = f"{base}.{ext}"
            if os.path.exists(candidate):
                filepath = candidate
                break

    return filepath


async def _download_direct(url: str, progress_cb: Optional[Callable]) -> str:
    """Stream-download a direct URL with progress."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36"
        )
    }
    file_id = f"direct_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
    filename = os.path.join(DOWNLOAD_DIR, file_id)
    last_update = 0.0

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=httpx.Timeout(90.0, connect=15.0)) as session:
        async with session.stream("GET", url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(filename, "wb") as f:
                async for chunk in resp.aiter_bytes(1048576):  # High-speed 1MB chunk buffer
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.monotonic()
                    if progress_cb and (now - last_update) >= 2.5:
                        last_update = now
                        await progress_cb(downloaded, total)

    return filename
