"""Force-Subscribe (FSUB) helper for Telegram channel membership."""
from __future__ import annotations

import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import FSUB_CHANNEL, FSUB_CHANNEL_URL, ADMIN_IDS

logger = logging.getLogger(__name__)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Return True if FSUB is disabled, or user is an admin or joined the channel."""
    if not FSUB_CHANNEL:
        return True

    if user_id in ADMIN_IDS:
        return True

    target_channel = FSUB_CHANNEL
    if target_channel.lstrip("-").isdigit():
        target_channel = int(target_channel)

    try:
        member = await bot.get_chat_member(chat_id=target_channel, user_id=user_id)
        status = getattr(member, "status", "")
        if status in ("creator", "administrator", "member"):
            return True
        if status == "restricted" and getattr(member, "is_member", True):
            return True
        return False
    except Exception as e:
        # If bot is not an admin in channel or invalid config, log and fail-open
        logger.warning(f"FSUB check failed for user {user_id} in channel '{FSUB_CHANNEL}': {e}")
        return True


def get_fsub_keyboard() -> InlineKeyboardMarkup:
    """Return inline keyboard with Join Channel and Verify buttons."""
    join_url = FSUB_CHANNEL_URL
    if not join_url and FSUB_CHANNEL.startswith("@"):
        join_url = f"https://t.me/{FSUB_CHANNEL.lstrip('@')}"

    buttons = []
    if join_url:
        buttons.append([InlineKeyboardButton("📢 Join Updates Channel", url=join_url)])
    buttons.append([InlineKeyboardButton("🔄 Joined — Check Membership", callback_data="check_fsub")])
    return InlineKeyboardMarkup(buttons)


def get_fsub_message() -> str:
    """Return friendly message explaining channel membership requirement."""
    return (
        "📢 <b>Access Restricted!</b>\n\n"
        "You must join our official updates channel to use this bot.\n\n"
        "1️⃣ Tap <b>Join Updates Channel</b> below.\n"
        "2️⃣ Tap <b>Joined — Check Membership</b> to unlock the bot! 🚀"
    )
