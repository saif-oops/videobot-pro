"""Telegram message progress bar updater."""
from __future__ import annotations

import html
import time
from telegram import Message


class ProgressBar:
    """Edits a Telegram message to show live download progress using HTML formatting."""

    BAR_LENGTH = 18

    def __init__(self, message: Message, title: str):
        self.message = message
        self.title = title[:50]
        self._last_update = 0.0
        self._update_interval = 3.0   # seconds between Telegram edits

    async def update(self, downloaded: int, total: int):
        """Call this with current downloaded bytes and total bytes."""
        now = time.monotonic()
        if now - self._last_update < self._update_interval:
            return
        self._last_update = now
        await self._edit(downloaded, total)

    async def _edit(self, downloaded: int, total: int):
        if total > 0:
            pct = min(int(downloaded / total * 100), 100)
            filled = int(pct / 100 * self.BAR_LENGTH)
            bar = "█" * filled + "░" * (self.BAR_LENGTH - filled)
            dl_mb = downloaded / (1024 ** 2)
            total_mb = total / (1024 ** 2)
            size_str = f"{dl_mb:.1f} MB / {total_mb:.1f} MB"
        else:
            pct = 0
            bar = "░" * self.BAR_LENGTH
            dl_mb = downloaded / (1024 ** 2)
            size_str = f"{dl_mb:.1f} MB / ?"

        esc_title = html.escape(self.title)
        text = (
            f"⬇️ <b>Downloading…</b>\n\n"
            f"📹 <i>{esc_title}</i>\n\n"
            f"<code>[{bar}]</code> <b>{pct}%</b>\n"
            f"📦 {size_str}"
        )
        try:
            await self.message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass  # ignore rate-limit errors

    async def done(self, filesize_mb: float):
        bar = "█" * self.BAR_LENGTH
        esc_title = html.escape(self.title)
        text = (
            f"✅ <b>Download Complete!</b>\n\n"
            f"📹 <i>{esc_title}</i>\n\n"
            f"<code>[{bar}]</code> <b>100%</b>\n"
            f"📦 {filesize_mb:.1f} MB\n\n"
            f"📤 Sending to Telegram…"
        )
        try:
            await self.message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

    async def sending(self):
        try:
            await self.message.edit_text(
                "📤 <b>Sending to Telegram…</b>\n<i>(large files may take a moment)</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass
