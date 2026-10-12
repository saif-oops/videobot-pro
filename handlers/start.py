"""Start, help, and status handlers."""
from __future__ import annotations

import os
import html
from telegram import Update
from telegram.ext import ContextTypes

from config import BOT_NAME, FREE_QUOTA, PREMIUM_PRICE_INR
from database.models import get_or_create_user, get_user


START_TEXT = (
    "👋 <b>Welcome to {name}!</b>\n\n"
    "I can <b>play</b> and <b>download</b> videos from:\n"
    "  📦 <b>Terabox</b>\n"
    "  💾 <b>DiskWala</b>\n\n"
    "🎫 You get <b>{quota} free videos</b> to try.\n"
    "🌟 Upgrade to <b>Premium</b> (₹{price} Lifetime) for unlimited access.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📌 <b>How to use:</b>\n"
    "  Just send me any Terabox or DiskWala link!\n\n"
    "⚙️ <b>Commands:</b>\n"
    "  /start — Show this message\n"
    "  /status — Your account status\n"
    "  /premium — Buy premium\n"
    "  /help — Help & FAQ\n"
)

HELP_TEXT = (
    "❓ <b>Help & FAQ</b>\n\n"
    "<b>Q: How do I use the bot?</b>\n"
    "A: Just paste a Terabox or DiskWala link. The bot will show the video info and let you play online or download it.\n\n"
    "<b>Q: What's the free limit?</b>\n"
    f"A: {FREE_QUOTA} free video plays/downloads. After that, upgrade to Premium.\n\n"
    "<b>Q: What does Premium include?</b>\n"
    "A: Unlimited plays & downloads, all qualities, forever — one-time ₹99 payment.\n\n"
    "<b>Q: How do I pay?</b>\n"
    "A: Use /premium to get a secure Razorpay payment link.\n\n"
    "<b>Q: Is payment safe?</b>\n"
    "A: Yes! We use Razorpay, India's most trusted payment gateway.\n\n"
    "<b>Q: My video isn't working?</b>\n"
    "A: Make sure the link is valid and has not expired or been deleted by the owner.\n"
    "Telegram has a 50MB file size limit for direct bot uploads, but you can always use the 'Watch Online' button."
)


async def start_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.username or "", user.full_name)

    text = START_TEXT.format(
        name=BOT_NAME,
        quota=FREE_QUOTA,
        price=PREMIUM_PRICE_INR,
    )

    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot_icon.jpg")
    if os.path.exists(icon_path):
        try:
            with open(icon_path, "rb") as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=text,
                    parse_mode="HTML",
                )
                return
        except Exception:
            pass  # Fall back to text if photo send fails

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )


async def help_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")


async def status_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_user(user.id)

    if not db_user:
        await update.message.reply_text("Please send /start first.")
        return

    if db_user["is_premium"]:
        tier = "🌟 <b>Premium</b> (Lifetime)"
        quota_line = "✅ Unlimited plays & downloads"
    else:
        remaining = db_user["free_uses"]
        tier = "🎫 <b>Free</b>"
        bar_filled = min(5 - remaining, 5)
        bar = "🟥" * bar_filled + "⬜" * remaining
        quota_line = f"{bar} {remaining}/5 free uses left"

    text = (
        f"👤 <b>Account Status</b>\n\n"
        f"📛 Name: {html.escape(user.full_name)}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📊 Tier: {tier}\n"
        f"🎬 {quota_line}\n"
        f"📥 Total downloads: {db_user['total_uses']}\n"
    )

    if not db_user["is_premium"]:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌟 Upgrade to Premium — ₹99", callback_data="goto_premium")
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML")
