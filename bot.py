"""Main bot entry point with Starlette/Uvicorn webhook server for Razorpay."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import socket
import threading
from urllib.parse import urlparse

# ─── Python 3.14 Compatibility Patch ─────────────────────────
# Bypasses anyio Happy Eyeballs task group deadlock on Python 3.14 alpha
import anyio
import anyio._core._sockets

async def _patched_connect_tcp(remote_host, remote_port, **kwargs):
    backend = anyio._core._eventloop.get_async_backend()
    return await backend.connect_tcp(str(remote_host), remote_port)

anyio.connect_tcp = _patched_connect_tcp
anyio._core._sockets.connect_tcp = _patched_connect_tcp
# ─────────────────────────────────────────────────────────────

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    FileResponse, HTMLResponse, JSONResponse,
    PlainTextResponse, Response, StreamingResponse,
)
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from config import BOT_TOKEN, PORT, WEBHOOK_URL, ALLOWED_STREAM_DOMAINS
from database.db import init_db
from handlers.start import start_handler, help_handler, status_handler
from handlers.video import link_handler, callback_handler
from handlers.payment import (
    premium_command, verify_razorpay_webhook, process_payment_webhook,
)
from handlers.admin import (
    admin_panel, stats_command, grant_command, revoke_command,
    addquota_command, ban_command, unban_command,
    lookup_command, broadcast_command,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Global PTB app reference (set in main)
_ptb_app: Application | None = None

# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")


# ─── Build PTB Application ────────────────────────────────────

def build_ptb_app() -> Application:
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=16,
        connect_timeout=30.0,
        read_timeout=120.0,
        write_timeout=300.0,
    )
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    # ── User commands ──
    app.add_handler(CommandHandler("start",   start_handler))
    app.add_handler(CommandHandler("help",    help_handler))
    app.add_handler(CommandHandler("status",  status_handler))
    app.add_handler(CommandHandler("premium", premium_command))

    # ── Admin commands ──
    app.add_handler(CommandHandler("admin",     admin_panel))
    app.add_handler(CommandHandler("stats",     stats_command))
    app.add_handler(CommandHandler("grant",     grant_command))
    app.add_handler(CommandHandler("revoke",    revoke_command))
    app.add_handler(CommandHandler("addquota",  addquota_command))
    app.add_handler(CommandHandler("ban",       ban_command))
    app.add_handler(CommandHandler("unban",     unban_command))
    app.add_handler(CommandHandler("lookup",    lookup_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    # ── Callbacks ──
    app.add_handler(CallbackQueryHandler(callback_handler))

    # ── Link messages ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_handler))

    return app


# ─── Starlette Web Routes ─────────────────────────────────────

async def health(request: Request):
    return PlainTextResponse("OK")


async def razorpay_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")

    if not await verify_razorpay_webhook(body, signature):
        logger.warning("Invalid Razorpay webhook signature")
        return PlainTextResponse("Invalid signature", status_code=400)

    try:
        payload = json.loads(body)
    except Exception:
        return PlainTextResponse("Invalid JSON", status_code=400)

    logger.info(f"Razorpay webhook: {payload.get('event')}")
    if _ptb_app:
        await process_payment_webhook(payload, _ptb_app.bot)
    return PlainTextResponse("OK")


async def telegram_webhook(request: Request):
    body = await request.body()
    update = Update.de_json(json.loads(body), _ptb_app.bot)
    await _ptb_app.process_update(update)
    return PlainTextResponse("OK")


async def payment_success(request: Request):
    return HTMLResponse("""
    <html>
    <head><title>Payment Successful</title></head>
    <body style="font-family:sans-serif;text-align:center;padding:60px;background:#f0f4f8">
      <div style="background:white;padding:40px;border-radius:16px;max-width:400px;margin:auto;box-shadow:0 4px 20px rgba(0,0,0,.1)">
        <div style="font-size:60px">🎉</div>
        <h2 style="color:#22c55e">Payment Successful!</h2>
        <p>Your <strong>VideoBot Pro Premium</strong> will be activated within a few minutes.</p>
        <p>Return to Telegram and send <code>/status</code> to confirm.</p>
      </div>
    </body>
    </html>
    """)


# ─── Player Page & Static Serving ─────────────────────────────

async def player_page(request: Request):
    """Serve the custom video player SPA directly without anyio thread deadlock on Python 3.14."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    except Exception as e:
        return PlainTextResponse(f"Player load error: {e}", status_code=500)


async def static_file(request: Request):
    """Serve static assets directly without anyio thread deadlock on Python 3.14."""
    filename = request.path_params.get("filename", "")
    safe_path = os.path.normpath(os.path.join(STATIC_DIR, filename))
    if not safe_path.startswith(STATIC_DIR) or not os.path.isfile(safe_path):
        return PlainTextResponse("Not Found", status_code=404)

    ext = os.path.splitext(safe_path)[1].lower()
    media_types = {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".json": "application/json",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    try:
        with open(safe_path, "rb") as f:
            content = f.read()
        return Response(content, media_type=media_type, headers={"Cache-Control": "public, max-age=3600"})
    except Exception as e:
        return PlainTextResponse(f"Static file error: {e}", status_code=500)


# ─── API: Fetch Video Info ────────────────────────────────────

async def api_fetch(request: Request):
    """POST /api/fetch — Extract video metadata and stream URL."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    url = body.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "Missing 'url' field"}, status_code=400)

    from utils.downloader import detect_platform
    if not detect_platform(url):
        return JSONResponse(
            {"error": "Only TeraBox and DiskWala links are supported"},
            status_code=400,
            headers=_cors_headers(),
        )

    try:
        from utils.downloader import get_video_info
        info = await get_video_info(url)
        return JSONResponse(info, headers=_cors_headers())
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=422, headers=_cors_headers())
    except Exception as e:
        logger.exception("api_fetch error")
        return JSONResponse({"error": f"Failed to fetch: {e}"}, status_code=500, headers=_cors_headers())


# ─── SSRF Protection Validator ───────────────────────────────

def is_safe_proxy_url(url: str) -> tuple[bool, str]:
    """Validate target URL to strictly prevent SSRF, DNS rebinding, and LAN probing."""
    if not url or not isinstance(url, str):
        return False, "Missing URL"
    if len(url) > 4096:
        return False, "URL length exceeds limit"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL"

    if parsed.scheme != "https":
        return False, "Only HTTPS streams are permitted"

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "Missing hostname"

    # Block credentials in URL (e.g., https://user:pass@domain)
    if parsed.username or parsed.password:
        return False, "Userinfo in URL is not allowed"

    # Enforce standard HTTPS port (443 or omitted)
    if parsed.port and parsed.port != 443:
        return False, f"Disallowed port: {parsed.port}"

    # Match hostname against allowed domain suffixes
    domain_allowed = any(
        hostname == d or hostname.endswith("." + d)
        for d in ALLOWED_STREAM_DOMAINS
    )
    if not domain_allowed:
        return False, f"Domain '{hostname}' is not allowed"

    # Resolve IP and verify it is not private, loopback, link-local, or reserved
    try:
        addr_info = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
        if not addr_info:
            return False, "DNS resolution returned no addresses"
        for entry in addr_info:
            ip_str = entry[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_unspecified
            ):
                return False, f"Resolved IP '{ip_str}' is forbidden"
    except Exception as e:
        return False, f"DNS resolution failed: {e}"

    return True, ""


async def _check_redirect(response: httpx.Response):
    """Event hook to validate HTTP redirect hops against SSRF rules."""
    if response.is_redirect and "location" in response.headers:
        loc = response.headers["location"]
        redir_target = str(response.url.join(loc))
        safe, reason = is_safe_proxy_url(redir_target)
        if not safe:
            raise httpx.RequestError(f"Disallowed redirect target: {reason}")


# ─── API: Stream Proxy ───────────────────────────────────────

_PROXY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


async def api_stream(request: Request):
    """GET /api/stream?url=... — CORS-safe stream proxy for video playback."""
    target_url = request.query_params.get("url", "").strip()
    if not target_url:
        return PlainTextResponse("Missing 'url' param", status_code=400)

    safe, reason = is_safe_proxy_url(target_url)
    if not safe:
        logger.warning(f"SSRF attempt blocked in api_stream: {reason} for URL: {target_url[:120]}")
        return PlainTextResponse(f"Forbidden: {reason}", status_code=403)

    # Determine content type from URL
    is_hls = "m3u8" in target_url.lower()

    # Pass range headers for seeking support
    range_header = request.headers.get("range")
    proxy_headers = dict(_PROXY_HEADERS)
    if "teraboxdl" in target_url:
        proxy_headers["Referer"] = "https://playterabox.com/"
    elif "1024tera" in target_url or "terabox" in target_url:
        proxy_headers["Referer"] = "https://www.1024tera.com/"

    if range_header:
        proxy_headers["Range"] = range_header

    client = None
    try:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=60.0,
            event_hooks={"response": [_check_redirect]},
        )
        resp = await client.send(
            client.build_request("GET", target_url, headers=proxy_headers),
            stream=True,
        )

        # Build response headers
        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Range",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Cache-Control": "no-cache",
        }

        if is_hls:
            resp_headers["Content-Type"] = "application/vnd.apple.mpegurl"
        else:
            ct = resp.headers.get("content-type", "video/mp4")
            resp_headers["Content-Type"] = ct

        # Forward content-length and range headers
        if "content-length" in resp.headers:
            resp_headers["Content-Length"] = resp.headers["content-length"]
        if "content-range" in resp.headers:
            resp_headers["Content-Range"] = resp.headers["content-range"]
        if "accept-ranges" in resp.headers:
            resp_headers["Accept-Ranges"] = resp.headers["accept-ranges"]

        async def stream_body():
            try:
                async for chunk in resp.aiter_bytes(65536):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        status_code = resp.status_code
        return StreamingResponse(
            stream_body(),
            status_code=status_code,
            headers=resp_headers,
        )
    except Exception as e:
        if client:
            await client.aclose()
        logger.exception("api_stream error")
        return PlainTextResponse(f"Stream error: {e}", status_code=502)


# ─── API: Download Proxy ─────────────────────────────────────

async def api_download(request: Request):
    """GET /api/download?url=...&title=... — Stream as downloadable attachment."""
    target_url = request.query_params.get("url", "").strip()
    title = request.query_params.get("title", "video")
    if not target_url:
        return PlainTextResponse("Missing 'url' param", status_code=400)

    safe, reason = is_safe_proxy_url(target_url)
    if not safe:
        logger.warning(f"SSRF attempt blocked in api_download: {reason} for URL: {target_url[:120]}")
        return PlainTextResponse(f"Forbidden: {reason}", status_code=403)

    # Sanitize filename
    safe_title = re.sub(r'[^\w\s\-.]', '', title)[:60] or "video"

    proxy_headers = dict(_PROXY_HEADERS)
    if "teraboxdl" in target_url:
        proxy_headers["Referer"] = "https://playterabox.com/"
    elif "1024tera" in target_url or "terabox" in target_url:
        proxy_headers["Referer"] = "https://www.1024tera.com/"

    client = None
    try:
        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=120.0,
            event_hooks={"response": [_check_redirect]},
        )
        resp = await client.send(
            client.build_request("GET", target_url, headers=proxy_headers),
            stream=True,
        )

        resp_headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Disposition": f'attachment; filename="{safe_title}.mp4"',
            "Content-Type": "video/mp4",
        }

        if "content-length" in resp.headers:
            resp_headers["Content-Length"] = resp.headers["content-length"]

        async def stream_body():
            try:
                async for chunk in resp.aiter_bytes(65536):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(stream_body(), headers=resp_headers)
    except Exception as e:
        if client:
            await client.aclose()
        logger.exception("api_download error")
        return PlainTextResponse(f"Download error: {e}", status_code=502)



# ─── CORS preflight handler ──────────────────────────────────

async def cors_preflight(request: Request):
    return PlainTextResponse("OK", headers=_cors_headers())


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Range",
    }


# ─── Build Starlette App ─────────────────────────────────────

def create_starlette_app(webhook_mode: bool) -> Starlette:
    routes = [
        # Existing routes
        Route("/",                  health),
        Route("/webhook/razorpay",  razorpay_webhook, methods=["POST"]),
        Route("/payment/success",   payment_success),

        # Player routes
        Route("/player",            player_page),

        # API routes
        Route("/api/fetch",         api_fetch, methods=["POST", "OPTIONS"]),
        Route("/api/stream",        api_stream, methods=["GET", "OPTIONS"]),
        Route("/api/download",      api_download, methods=["GET"]),

        # Static files (CSS, JS, etc.)
        Route("/static/{filename:path}", static_file),
    ]
    if webhook_mode:
        routes.append(Route("/telegram/webhook", telegram_webhook, methods=["POST"]))
    return Starlette(routes=routes)


# ─── Auto-Delete Background Worker ────────────────────────────

async def _auto_delete_worker(app: Application):
    """Background worker that continuously deletes expired scheduled messages."""
    from database.models import get_due_deletions, remove_scheduled_deletion
    logger.info("Auto-delete worker started ⏳")
    while True:
        try:
            due_items = await get_due_deletions()
            for item in due_items:
                rec_id = item["id"]
                chat_id = item["chat_id"]
                msg_id = item["message_id"]
                try:
                    await app.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    logger.info(f"Auto-deleted message {msg_id} in chat {chat_id} 🧹")
                except Exception as e:
                    # Message may already be deleted by user or expired
                    logger.debug(f"Could not delete message {msg_id}: {e}")
                finally:
                    await remove_scheduled_deletion(rec_id)
        except Exception as e:
            logger.error(f"Error in auto-delete worker: {e}")
        await asyncio.sleep(10)


# ─── Main ─────────────────────────────────────────────────────

async def main():
    global _ptb_app

    # Initialize database
    await init_db()
    logger.info("Database initialized ✅")

    _ptb_app = build_ptb_app()
    for attempt in range(1, 6):
        try:
            await _ptb_app.initialize()
            await _ptb_app.start()
            try:
                me = await _ptb_app.bot.get_me()
                logger.info(f"Connected to bot: @{me.username} ({me.first_name}) 🤖")
            except Exception as e:
                logger.warning(f"Could not fetch bot identity: {e}")
            break
        except Exception as e:
            logger.warning(f"PTB start attempt {attempt} failed: {e}. Retrying in 3s...")
            await asyncio.sleep(3)

    # Start auto-delete background worker
    auto_delete_task = asyncio.create_task(_auto_delete_worker(_ptb_app))

    # Set up Mini App menu button pointing to our custom player
    from telegram import MenuButtonWebApp, WebAppInfo
    from config import TERABOX_WEBAPP_URL
    if TERABOX_WEBAPP_URL.startswith("https://"):
        try:
            await _ptb_app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="▶ TeraPlayer", web_app=WebAppInfo(url=TERABOX_WEBAPP_URL))
            )
            logger.info("Chat menu button → TeraPlayer Mini App 🚀")
        except Exception as e:
            logger.warning(f"Could not set chat menu button: {e}")
    else:
        logger.info("Chat menu button: TERABOX_WEBAPP_URL is not HTTPS (dev mode). WebApp menu button skipped.")

    webhook_mode = bool(WEBHOOK_URL)

    # Build Starlette app
    starlette_app = create_starlette_app(webhook_mode)

    if webhook_mode:
        # Production: Telegram webhook
        webhook_url = f"{WEBHOOK_URL.rstrip('/')}/telegram/webhook"
        await _ptb_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Telegram webhook set: {webhook_url}")
    else:
        # Development: polling
        logger.info("Starting bot in polling mode 🔄")
        await _ptb_app.updater.start_polling(drop_pending_updates=True)

    # Run uvicorn in a separate thread to avoid event loop conflicts
    config = uvicorn.Config(
        app=starlette_app,
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    logger.info(f"Web server starting on port {PORT} 🌐")
    logger.info(f"Player available at http://localhost:{PORT}/player")

    try:
        await server.serve()
    finally:
        auto_delete_task.cancel()
        if not webhook_mode:
            await _ptb_app.updater.stop()
        await _ptb_app.stop()
        await _ptb_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
