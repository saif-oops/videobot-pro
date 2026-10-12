"""Admin panel commands — only accessible by ADMIN_IDS."""
from __future__ import annotations

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database.models import (
    get_stats, get_user, get_all_user_ids,
    grant_premium, revoke_premium, add_free_quota,
    ban_user, unban_user, search_user,
)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def admin_only(func):
    """Decorator to restrict handlers to admins."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ Admin only command.")
            return
        return await func(update, ctx)
    return wrapper


# ─── /admin ───────────────────────────────────────────────────

@admin_only
async def admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stats = await get_stats()
    text = (
        "🛡️ *Admin Panel*\n\n"
        f"👥 Total Users: *{stats['total_users']}*\n"
        f"🌟 Premium Users: *{stats['premium_users']}*\n"
        f"⛔ Banned: *{stats['banned_users']}*\n\n"
        f"📥 Downloads Today: *{stats['downloads_today']}*\n"
        f"📊 Total Downloads: *{stats['total_downloads']}*\n"
        f"💰 Total Payments: *{stats['total_paid']}*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *Commands:*\n"
        "/grant @username — Give premium\n"
        "/revoke @username — Remove premium\n"
        "/addquota @username 5 — Add free uses\n"
        "/ban @username — Ban user\n"
        "/unban @username — Unban user\n"
        "/lookup @username — View user info\n"
        "/broadcast message — Send to all users\n"
        "/stats — Show this panel\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /stats ───────────────────────────────────────────────────

@admin_only
async def stats_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await admin_panel(update, ctx)


# ─── /grant ───────────────────────────────────────────────────

@admin_only
async def grant_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /grant @username or /grant user_id")
        return

    target = args[0].lstrip("@")
    user = await _resolve_target(target)

    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    await grant_premium(user["user_id"])
    await update.message.reply_text(
        f"✅ Premium granted to *{user['full_name']}* (ID: `{user['user_id']}`).",
        parse_mode="Markdown"
    )

    # Notify the user
    try:
        from telegram import Bot
        await ctx.bot.send_message(
            chat_id=user["user_id"],
            text=(
                "🎉 *Premium Activated!*\n\n"
                "Your account has been upgraded to *Lifetime Premium* by admin.\n"
                "Enjoy unlimited downloads! 🚀"
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ─── /revoke ──────────────────────────────────────────────────

@admin_only
async def revoke_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /revoke @username or /revoke user_id")
        return

    target = args[0].lstrip("@")
    user = await _resolve_target(target)

    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    await revoke_premium(user["user_id"])
    await update.message.reply_text(
        f"✅ Premium revoked from *{user['full_name']}*.",
        parse_mode="Markdown"
    )


# ─── /addquota ────────────────────────────────────────────────

@admin_only
async def addquota_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /addquota @username 5")
        return

    target = args[0].lstrip("@")
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return

    user = await _resolve_target(target)
    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    await add_free_quota(user["user_id"], amount)
    await update.message.reply_text(
        f"✅ Added *{amount}* free uses to *{user['full_name']}*.",
        parse_mode="Markdown"
    )


# ─── /ban ─────────────────────────────────────────────────────

@admin_only
async def ban_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /ban @username or /ban user_id")
        return

    target = args[0].lstrip("@")
    user = await _resolve_target(target)
    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    await ban_user(user["user_id"])
    await update.message.reply_text(
        f"⛔ Banned *{user['full_name']}* (ID: `{user['user_id']}`).",
        parse_mode="Markdown"
    )


# ─── /unban ───────────────────────────────────────────────────

@admin_only
async def unban_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /unban @username or /unban user_id")
        return

    target = args[0].lstrip("@")
    user = await _resolve_target(target)
    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    await unban_user(user["user_id"])
    await update.message.reply_text(
        f"✅ Unbanned *{user['full_name']}*.",
        parse_mode="Markdown"
    )


# ─── /lookup ──────────────────────────────────────────────────

@admin_only
async def lookup_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /lookup @username or /lookup user_id")
        return

    target = args[0].lstrip("@")
    user = await _resolve_target(target)
    if not user:
        await update.message.reply_text(f"❌ User `{target}` not found.", parse_mode="Markdown")
        return

    tier = "🌟 Premium" if user["is_premium"] else "🎫 Free"
    banned = "⛔ Banned" if user["is_banned"] else "✅ Active"
    text = (
        f"👤 *User Info*\n\n"
        f"📛 Name: {user['full_name']}\n"
        f"🔖 Username: @{user['username'] or 'N/A'}\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"📊 Tier: {tier}\n"
        f"🎫 Free Uses Left: {user['free_uses']}\n"
        f"📥 Total Downloads: {user['total_uses']}\n"
        f"📅 Joined: {user['joined_at']}\n"
        f"🚦 Status: {banned}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── /broadcast ───────────────────────────────────────────────

@admin_only
async def broadcast_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: /broadcast Your message here\n"
            "Supports Markdown formatting."
        )
        return

    message = " ".join(ctx.args)
    user_ids = await get_all_user_ids()

    status_msg = await update.message.reply_text(
        f"📢 Broadcasting to {len(user_ids)} users…"
    )

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await ctx.bot.send_message(
                chat_id=uid,
                text=f"📢 *Announcement*\n\n{message}",
                parse_mode="Markdown"
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Avoid Telegram rate limits

    await status_msg.edit_text(
        f"✅ Broadcast complete!\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# ─── Helper ───────────────────────────────────────────────────

async def _resolve_target(target: str) -> dict | None:
    """Resolve username or user_id string to user dict."""
    if target.isdigit():
        return await get_user(int(target))
    return await search_user(target)
