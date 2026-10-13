"""Start, help, and status handlers."""
from __future__ import annotations

import os
import html
from telegram import Update
from telegram.ext import ContextTypes

from config import BOT_NAME, FREE_QUOTA, PREMIUM_PRICE_INR
from database.models import (
    get_or_create_user, get_user, process_referral_join, get_referral_stats,
)


START_TEXT = (
    "👋 <b>Welcome to {name}!</b>\n\n"
    "I can <b>play</b> and <b>download</b> videos from:\n"
    "  📦 <b>Terabox</b>\n"
    "  💾 <b>DiskWala</b>\n\n"
    "🎫 You get <b>{quota} free videos</b> to try.\n"
    "🌟 Upgrade to <b>Premium</b> (₹{price} / Month) for unlimited access.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📌 <b>How to use:</b>\n"
    "  Just send me any Terabox or DiskWala link!\n\n"
    "⚙️ <b>Commands:</b>\n"
    "  /start — Show this message\n"
    "  /refer — Invite friends & earn free uses\n"
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
    "<b>Q: How do I earn free downloads without paying?</b>\n"
    "A: Use /refer to get your personal invite link! You get +2 free downloads for every friend who joins, and 3 days of Free Premium for every 5 friends.\n\n"
    "<b>Q: What does Premium include?</b>\n"
    "A: Unlimited plays & downloads, all qualities — ₹99 per month (30 days validity).\n\n"
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

    # Check for referral parameter in /start ref_<id>
    referrer_id = None
    ref_param = ctx.args[0] if (ctx.args and len(ctx.args) > 0) else ""
    if ref_param.startswith("ref_"):
        raw_id = ref_param.replace("ref_", "").strip()
        if raw_id.isdigit():
            referrer_id = int(raw_id)

    bonus_msg = ""
    if referrer_id:
        db_user, was_awarded, milestone = await process_referral_join(
            referrer_id, user.id, user.username or "", user.full_name
        )
        if was_awarded:
            bonus_msg = "🎁 <b>Referral Bonus:</b> You received <b>+1 Extra Free Download</b> for using an invite link! (6 total free uses)\n\n"
            try:
                milestone_txt = "\n\n🌟 <b>Milestone Achieved!</b> You invited 5 friends and earned <b>3 Days of Free Premium</b>! 🚀" if milestone else ""
                await ctx.bot.send_message(
                    chat_id=referrer_id,
                    text=(
                        f"🎉 <b>New Referral Joined!</b>\n\n"
                        f"👤 <b>{html.escape(user.full_name)}</b> (@{user.username or 'user'}) joined using your invite link.\n"
                        f"🎁 You've earned <b>+2 Free Video Uses</b>! ⚡{milestone_txt}"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass
    else:
        await get_or_create_user(user.id, user.username or "", user.full_name)

    from utils.fsub import is_subscribed, get_fsub_keyboard, get_fsub_message
    if not await is_subscribed(ctx.bot, user.id):
        await update.message.reply_text(
            get_fsub_message(),
            parse_mode="HTML",
            reply_markup=get_fsub_keyboard(),
        )
        return

    text = bonus_msg + START_TEXT.format(
        name=BOT_NAME,
        quota=FREE_QUOTA + (1 if bonus_msg else 0),
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
        expiry_info = ""
        if db_user.get("premium_until"):
            expiry_info = f"\n⏳ <b>Expires:</b> <code>{db_user['premium_until']}</code>"
        tier = f"🌟 <b>Premium</b> (Monthly Plan){expiry_info}"
        quota_line = "✅ Unlimited plays & downloads"
    else:
        remaining = db_user["free_uses"]
        tier = "🎫 <b>Free Tier</b>"
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
            InlineKeyboardButton("🌟 Upgrade to Premium — ₹99/mo", callback_data="goto_premium")
        ]])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode="HTML")


async def refer_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Display referral dashboard with unique link, stats, and 1-tap share button."""
    user = update.effective_user
    await get_or_create_user(user.id, user.username or "", user.full_name)
    stats = await get_referral_stats(user.id)

    try:
        me = await ctx.bot.get_me()
        bot_uname = me.username or "Tera_Player_Bot"
    except Exception:
        bot_uname = "Tera_Player_Bot"

    ref_link = f"https://t.me/{bot_uname}?start=ref_{user.id}"
    from utils.keyboards import referral_keyboard
    kb = referral_keyboard(ref_link)

    text = (
        "🎁 <b>Referral & Rewards Program</b>\n\n"
        "Invite your friends to use <b>VideoBot Pro</b> and earn free downloads and premium access!\n\n"
        f"🔗 <b>Your Personal Invite Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "📊 <b>Your Referral Stats:</b>\n"
        f"👥 Friends Joined: <b>{stats['total_referred']}</b>\n"
        f"🎫 Bonus Uses Earned: <b>+{stats['bonus_uses']}</b>\n\n"
        "🏆 <b>Rewards:</b>\n"
        "• <b>+2 Free Uses</b> for every friend who joins\n"
        "• 🌟 <b>3 Days Free Premium</b> for every 5 friends!\n"
        "• Your friend receives <b>+1 Bonus Use</b> instantly\n\n"
        "<i>Tap below to share your link with friends or groups!</i>"
    )
    target = update.message or (update.callback_query.message if update.callback_query else None)
    if target:
        await target.reply_text(text, parse_mode="HTML", reply_markup=kb)


async def refresh_refer_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Callback to refresh referral stats."""
    query = update.callback_query
    user = query.from_user
    stats = await get_referral_stats(user.id)

    try:
        me = await ctx.bot.get_me()
        bot_uname = me.username or "Tera_Player_Bot"
    except Exception:
        bot_uname = "Tera_Player_Bot"

    ref_link = f"https://t.me/{bot_uname}?start=ref_{user.id}"
    from utils.keyboards import referral_keyboard
    kb = referral_keyboard(ref_link)

    text = (
        "🎁 <b>Referral & Rewards Program</b>\n\n"
        "Invite your friends to use <b>VideoBot Pro</b> and earn free downloads and premium access!\n\n"
        f"🔗 <b>Your Personal Invite Link:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "📊 <b>Your Referral Stats:</b>\n"
        f"👥 Friends Joined: <b>{stats['total_referred']}</b>\n"
        f"🎫 Bonus Uses Earned: <b>+{stats['bonus_uses']}</b>\n\n"
        "🏆 <b>Rewards:</b>\n"
        "• <b>+2 Free Uses</b> for every friend who joins\n"
        "• 🌟 <b>3 Days Free Premium</b> for every 5 friends!\n"
        "• Your friend receives <b>+1 Bonus Use</b> instantly\n\n"
        "<i>Tap below to share your link with friends or groups!</i>"
    )
    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        await query.answer("✅ Stats refreshed!")
    except Exception:
        await query.answer("Stats are already up to date!")
