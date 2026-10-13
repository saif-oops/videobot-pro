"""Force-Subscribe (FSUB) helper for Telegram channel membership."""
from __future__ import annotations

import html
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import FSUB_CHANNEL, FSUB_CHANNEL_URL, ADMIN_IDS
from database.models import get_setting

logger = logging.getLogger(__name__)


async def get_active_fsub_channel() -> tuple[str, str]:
    """Returns (channel_identifier, channel_join_url)."""
    db_ch = await get_setting("fsub_channel")
    ch = (db_ch or FSUB_CHANNEL or "").strip()
    if not ch:
        return "", ""

    # Normalize URLs like https://t.me/MyChannel or accidental @https://t.me/...
    for prefix in ("@https://t.me/", "@http://t.me/"):
        if ch.startswith(prefix):
            ch = "@" + ch[len(prefix):]
            break

    join_url = ""
    if ch.startswith("https://t.me/"):
        join_url = ch
        ch = "@" + ch.replace("https://t.me/", "").rstrip("/")
    elif ch.startswith("http://t.me/"):
        join_url = ch
        ch = "@" + ch.replace("http://t.me/", "").rstrip("/")
    elif ch.startswith("t.me/"):
        join_url = f"https://{ch}"
        ch = "@" + ch.replace("t.me/", "").rstrip("/")

    if not join_url:
        db_url = await get_setting("fsub_url")
        join_url = (db_url or FSUB_CHANNEL_URL or "").strip()
        if not join_url and ch.startswith("@"):
            join_url = f"https://t.me/{ch.lstrip('@')}"

    return ch, join_url


async def get_required_channel() -> str:
    """Returns the active force-subscribe channel username or ID, or empty string."""
    ch, _ = await get_active_fsub_channel()
    return ch


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Return True if FSUB is disabled, user is admin, or user is subscribed to channel."""
    if user_id in ADMIN_IDS:
        return True

    target_channel, _ = await get_active_fsub_channel()
    if not target_channel:
        return True

    chat_id = int(target_channel) if target_channel.lstrip("-").isdigit() else target_channel

    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        status = getattr(member, "status", "")
        if status in ("creator", "administrator", "member"):
            return True
        if status == "restricted" and getattr(member, "is_member", True):
            return True
        return False
    except Exception as e:
        err_str = str(e).lower()
        # If Telegram says user not found, they definitely have NOT joined
        if any(k in err_str for k in ("user not found", "participant_id_invalid", "user not member", "member not found")):
            return False
        logger.warning(f"FSUB check warning for user {user_id} in channel '{target_channel}': {e}")
        # If bot is not an admin in channel or channel is misconfigured, fail-open to avoid global deadlock
        return True


async def get_fsub_keyboard() -> InlineKeyboardMarkup:
    """Return inline keyboard with Join Channel and Verify buttons."""
    ch, join_url = await get_active_fsub_channel()
    buttons = []
    if join_url:
        buttons.append([InlineKeyboardButton("📢 Join Updates Channel", url=join_url)])
    buttons.append([InlineKeyboardButton("🔄 Joined — Check Membership", callback_data="check_fsub")])
    return InlineKeyboardMarkup(buttons)


async def get_fsub_message() -> str:
    """Return friendly message explaining channel membership requirement."""
    ch, _ = await get_active_fsub_channel()
    ch_label = f"<b>{html.escape(ch)}</b>" if ch else "our official channel"
    return (
        "🔒 <b>Access Restricted!</b>\n\n"
        f"You must join {ch_label} before you can use this bot.\n\n"
        "1️⃣ Tap <b>📢 Join Updates Channel</b> below.\n"
        "2️⃣ Tap <b>Join</b> in Telegram.\n"
        "3️⃣ Tap <b>🔄 Joined — Check Membership</b> to unlock the bot! 🚀"
    )
