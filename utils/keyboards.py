"""Keyboards and message templates shared across handlers."""
from __future__ import annotations

import html
from urllib.parse import quote
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import TERABOX_WEBAPP_URL


# ─── Video Info Keyboard ──────────────────────────────────────

def video_action_keyboard(formats: list[dict], url_hash: str, web_url: str = "", original_url: str = "", user_id: int | None = None) -> InlineKeyboardMarkup:
    """Action keyboard: Play in Telegram and Watch Online (Mini App)."""
    rows = [
        [InlineKeyboardButton("✨ ▶️ Play in Telegram ✨", callback_data=f"play:{url_hash}:0")]
    ]
    target_url = original_url or web_url
    if TERABOX_WEBAPP_URL.startswith("https://") and target_url:
        uid_param = f"&uid={user_id}" if user_id else ""
        sid_param = f"&sid={url_hash}" if url_hash else ""
        player_link = f"{TERABOX_WEBAPP_URL}?url={quote(target_url, safe='')}{sid_param}{uid_param}"
        rows.append([
            InlineKeyboardButton("🌐 Watch Online", web_app=WebAppInfo(url=player_link))
        ])
    return InlineKeyboardMarkup(rows)


def selected_quality_keyboard(url_hash: str, fmt_idx: int,
                                label: str, web_url: str = "", original_url: str = "", user_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("✨ ▶️ Play in Telegram ✨", callback_data=f"play:{url_hash}:{fmt_idx}")]
    ]
    target_url = original_url or web_url
    if TERABOX_WEBAPP_URL.startswith("https://") and target_url:
        uid_param = f"&uid={user_id}" if user_id else ""
        sid_param = f"&sid={url_hash}" if url_hash else ""
        player_link = f"{TERABOX_WEBAPP_URL}?url={quote(target_url, safe='')}{sid_param}{uid_param}"
        rows.append([
            InlineKeyboardButton("🌐 Watch Online", web_app=WebAppInfo(url=player_link))
        ])
    return InlineKeyboardMarkup(rows)


def buy_premium_keyboard(payment_url: str = "") -> InlineKeyboardMarkup:
    from config import RAZORPAY_PAYMENT_URL
    rzp_url = payment_url or RAZORPAY_PAYMENT_URL or "https://rzp.io/rzp/1tGAGsc"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay via Razorpay (Instant VIP)", url=rzp_url)],
        [InlineKeyboardButton("📱 Pay via UPI / QR Code (0% Fee)", callback_data="pay_upi_qr")],
        [InlineKeyboardButton("🎁 Refer Friends — Earn Free Uses", callback_data="refresh_refer")],
        [InlineKeyboardButton("✅ I've Paid — Check Status", callback_data="verify_payment")],
    ])


def large_file_keyboard(original_url: str, direct_url: str, title: str, file_size_mb: float) -> InlineKeyboardMarkup:
    """Keyboard for files exceeding Telegram's 50MB bot upload limit."""
    rows = []
    target_url = original_url or direct_url
    if TERABOX_WEBAPP_URL.startswith("https://") and target_url:
        player_link = f"{TERABOX_WEBAPP_URL}?url={quote(target_url, safe='')}"
        rows.append([
            InlineKeyboardButton("🌐 Stream in Mini App", web_app=WebAppInfo(url=player_link))
        ])
        base_api = TERABOX_WEBAPP_URL.replace("/player", "").rstrip("/")
        if direct_url:
            dl_link = f"{base_api}/api/download?url={quote(direct_url, safe='')}&title={quote(title[:40], safe='')}"
            rows.append([
                InlineKeyboardButton(f"⬇️ Direct Browser Download ({file_size_mb:.0f} MB)", url=dl_link)
            ])
        else:
            rows.append([
                InlineKeyboardButton(f"⬇️ Open Download Page ({file_size_mb:.0f} MB)", url=player_link)
            ])
    elif direct_url:
        rows.append([
            InlineKeyboardButton(f"⬇️ Direct Download ({file_size_mb:.0f} MB)", url=direct_url)
        ])

    rows.append([InlineKeyboardButton("❌ Dismiss", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def referral_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    """Keyboard for /refer sharing and refresh."""
    share_text = quote("⚡ Stream and download TeraBox & DiskWala videos without 1-sec cuts or ads! Try this bot for free 👉 ")
    share_url = f"https://t.me/share/url?url={quote(invite_link)}&text={share_text}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Invite Link", url=share_url)],
        [InlineKeyboardButton("🔄 Refresh Stats", callback_data="refresh_refer")],
    ])


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
        if remaining > 0:
            quota_line = f"🎫 <b>Free Uses Remaining:</b> {remaining}/5"
        else:
            quota_line = (
                "⚠️ <b>Free Limit Reached (5/5 Used)!</b>\n"
                "<i>This was your 5th and final free unlock. Upgrade to Monthly VIP (/premium) to fetch more videos!</i>"
            )

    return (
        f"🎉 <b>Access Granted!</b> Your {platform} video is unlocked.\n\n"
        f"{emoji} <b>{title}</b>\n"
        f"⏱ <b>Duration:</b> {duration} | 📦 <b>Size:</b> {filesize}\n\n"
        f"{quota_line}\n\n"
        f"Tap below to play in Telegram 👇"
    )


def quota_exceeded_message() -> str:
    return (
        "❌ <b>Free Limit Reached (5/5 Used)!</b>\n\n"
        "You have used all <b>5 free video unlocks</b>.\n"
        "To continue fetching and streaming videos, please subscribe to <b>Monthly VIP</b>.\n\n"
        "🌟 <b>VideoBot Pro Premium — ₹99 / Month (30 Days)</b>\n"
        "✅ <b>Unlimited</b> video downloads & plays\n"
        "✅ <b>Zero ads</b> & zero countdown waits\n"
        "✅ Full 4K, 1080p & 720p stream qualities\n"
        "✅ Both TeraBox & DiskWala fully supported\n"
        "✅ High-speed cloud streaming\n\n"
        "👇 <b>Choose your payment method below:</b>"
    )
