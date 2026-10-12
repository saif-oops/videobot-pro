"""Keyboards and message templates shared across handlers."""
from __future__ import annotations

import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import TERABOX_WEBAPP_URL


# ─── Video Info Keyboard ──────────────────────────────────────

def video_action_keyboard(formats: list[dict], url_hash: str, web_url: str = "", original_url: str = "") -> InlineKeyboardMarkup:
    """Only one option below: Play with icon."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ ▶️ Play ✨", callback_data=f"play:{url_hash}:0")]
    ])


def selected_quality_keyboard(url_hash: str, fmt_idx: int,
                                label: str, web_url: str = "", original_url: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ ▶️ Play ✨", callback_data=f"play:{url_hash}:{fmt_idx}")]
    ])


def buy_premium_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💳 Pay ₹99 — Lifetime Premium", url=payment_url),
    ], [
        InlineKeyboardButton("✅ I've Paid — Verify", callback_data="verify_payment"),
    ]])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin:stats"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast"),
        ],
        [
            InlineKeyboardButton("👤 User Lookup", callback_data="admin:lookup"),
        ]
    ])


# ─── Message Templates ────────────────────────────────────────

PLATFORM_EMOJI = {
    "terabox": "📦",
    "diskwala": "💾",
    "unknown": "🎬",
}

def video_info_message(info: dict, user: dict) -> str:
    emoji = PLATFORM_EMOJI.get(info.get("platform", ""), "🎬")
    platform = info.get("platform", "unknown").capitalize()

    title = html.escape(info.get("title", "Video"))
    duration = html.escape(str(info.get("duration", "Unknown")))
    filesize = html.escape(str(info.get("filesize_str", "Unknown")))

    if user.get("is_premium"):
        quota_line = "🌟 <b>Premium Account</b> — Unlimited access"
    else:
        remaining = user.get("free_uses", 0)
        quota_line = f"🎫 <b>Free Uses Remaining:</b> {remaining}/5"

    return (
        f"🎉 <b>Access Granted!</b> Your {platform} video is unlocked.\n\n"
        f"{emoji} <b>{title}</b>\n"
        f"⏱ <b>Duration:</b> {duration} | 📦 <b>Size:</b> {filesize}\n\n"
        f"{quota_line}\n\n"
        f"Tap below to play in Telegram 👇"
    )


def quota_exceeded_message() -> str:
    return (
        "❌ <b>Free Limit Reached!</b>\n\n"
        "You've used all <b>5 free video plays/downloads</b>.\n\n"
        "🌟 Upgrade to <b>Premium</b> for just <b>₹99 Lifetime</b>\n"
        "✅ Unlimited downloads & plays\n"
        "✅ All platforms supported\n"
        "✅ Priority support\n\n"
        "👇 Tap below to pay securely via Razorpay:"
    )
