"""In-memory session store for pending video requests."""
from __future__ import annotations
import hashlib
import time
from typing import Optional

# { url_hash -> { 'info': dict, 'url': str, 'expires': float } }
_sessions: dict[str, dict] = {}
SESSION_TTL = 3600  # 1 hour


def store_session(url: str, info: dict) -> str:
    """Store video info and return a short hash key."""
    url_hash = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:12]
    _sessions[url_hash] = {
        "url": url,
        "info": info,
        "expires": time.time() + SESSION_TTL,
    }
    return url_hash


def get_session(url_hash: str) -> Optional[dict]:
    entry = _sessions.get(url_hash)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        del _sessions[url_hash]
        return None
    return entry


def cleanup():
    now = time.time()
    expired = [k for k, v in _sessions.items() if now > v["expires"]]
    for k in expired:
        del _sessions[k]
