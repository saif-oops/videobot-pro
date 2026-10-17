"""Admin panel commands — only accessible by ADMIN_IDS."""
from __future__ import annotations

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

from config import ADMIN_IDS
from database.models import (
    get_stats, get_user, get_all_user_ids,
    grant_premium, revoke_premium, add_free_quota,
    ban_user, unban_user, search_user,
    get_setting, set_setting, get_auto_delete_minutes,
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
    from utils.fsub import get_required_channel
    channel = await get_required_channel()
    fsub_display = channel if channel else "Disabled"
    del_mins = await get_auto_delete_minutes()
    del_display = f"{del_mins} min" if del_mins > 0 else "Disabled"

    text = (
        "🛡️ *Admin Panel*\n\n"
        f"👥 Total Users: *{stats['total_users']}*\n"
        f"🌟 Premium Users: *{stats['premium_users']}*\n"
        f"⛔ Banned: *{stats['banned_users']}*\n\n"
        f"📥 Downloads Today: *{stats['downloads_today']}*\n"
        f"📊 Total Downloads: *{stats['total_downloads']}*\n"
        f"💰 Total Payments: *{stats['total_paid']}*\n"
        f"🎁 Total Referrals: *{stats.get('total_referrals', 0)}*\n"
        f"📢 Required Channel: *{fsub_display}*\n"
        f"⏳ Auto-Delete: *{del_display}*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ *Commands:*\n"
        "/setchannel @channel — Set required channel (or 'off')\n"
        "/channel — Check current required channel\n"
        "/autodelete [mins] — Set auto-delete timer (e.g. 1, 30, 'off')\n"
        "/setad [tag/zone] — Set Monetag ad tag for Mini App\n"
        "/grant @username [days] — Give premium (default 30 days)\n"
        "/revoke @username — Remove premium\n"
        "/addquota @username 5 — Add free uses\n"
        "/ban @username — Ban user\n"
        "/unban @username — Unban user\n"
        "/lookup @username — View user info\n"
        "/broadcast message — Send to all users\n"
        "/backup — Export database snapshot\n"
        "/restore — Reply to .db file to restore\n"
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
        await update.message.reply_text("Usage: /grant @username [days] (default 30 days)")
        return

    target = args[0].lstrip("@")
    days = 30
    if len(args) > 1 and args[1].isdigit():
        days = int(args[1])

    user = await _resolve_target(target)
    if not user:
        await update.message.reply_text(
            f"❌ User `{target}` not found.\n\n"
            f"💡 *Tip:* You can also grant premium directly using their numeric User ID:\n"
            f"`/grant <user_id> [days]`\n"
            f"Example: `/grant 8993083780 30`",
            parse_mode="Markdown"
        )
        return

    await grant_premium(user["user_id"], days=days)
    await update.message.reply_text(
        f"✅ Premium ({days} days) granted to *{user['full_name']}* (ID: `{user['user_id']}`).",
        parse_mode="Markdown"
    )

    # Notify the user
    try:
        from telegram import Bot
        await ctx.bot.send_message(
            chat_id=user["user_id"],
            text=(
                "🎉 *Premium Activated!*\n\n"
                f"Your account has been upgraded to *Monthly Premium ({days} Days)* by admin.\n"
                "Enjoy unlimited downloads & streaming! 🚀"
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

    if user["is_premium"]:
        expiry = f" (Expires: {user['premium_until']})" if user.get("premium_until") else " (Active)"
        tier = f"🌟 Premium{expiry}"
    else:
        tier = "🎫 Free"
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
    reply_msg = update.message.reply_to_message
    text_msg = " ".join(ctx.args).strip() if ctx.args else ""

    if not reply_msg and not text_msg:
        await update.message.reply_text(
            "📢 <b>How to Broadcast:</b>\n\n"
            "1. <b>Text:</b> <code>/broadcast Your message here</code>\n"
            "2. <b>Media:</b> Reply to any photo, video, or post with <code>/broadcast</code>",
            parse_mode="HTML"
        )
        return

    user_ids = await get_all_user_ids()
    if not user_ids:
        await update.message.reply_text("ℹ️ No registered users found.")
        return

    status_msg = await update.message.reply_text(
        f"📢 Broadcasting to <b>{len(user_ids)}</b> users…",
        parse_mode="HTML"
    )

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            if reply_msg:
                await ctx.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=update.message.chat_id,
                    message_id=reply_msg.message_id,
                )
            else:
                await ctx.bot.send_message(
                    chat_id=uid,
                    text=f"📢 <b>Announcement</b>\n\n{text_msg}",
                    parse_mode="HTML"
                )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram rate-limiting

    await status_msg.edit_text(
        f"✅ <b>Broadcast complete!</b>\n\n"
        f"📤 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>",
        parse_mode="HTML"
    )


# ─── /backup ──────────────────────────────────────────────────

@admin_only
async def backup_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from database.db import DB_PATH, checkpoint_db
    import os
    from datetime import datetime

    status_msg = await update.message.reply_text("⏳ Creating database backup…")
    try:
        await checkpoint_db()
        if not os.path.exists(DB_PATH):
            await status_msg.edit_text("❌ Database file not found on disk.")
            return

        size_kb = os.path.getsize(DB_PATH) / 1024
        stats = await get_stats()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        caption = (
            "📦 <b>VideoBot Pro Database Backup</b>\n\n"
            f"📅 <b>Created:</b> <code>{timestamp}</code>\n"
            f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
            f"🌟 <b>Premium:</b> <code>{stats['premium_users']}</code>\n"
            f"📥 <b>Total Downloads:</b> <code>{stats['total_downloads']}</code>\n"
            f"💾 <b>Size:</b> <code>{size_kb:.1f} KB</code>\n\n"
            "<i>💡 To restore this backup, reply to this document with <code>/restore</code>.</i>"
        )

        with open(DB_PATH, "rb") as db_file:
            await ctx.bot.send_document(
                chat_id=update.effective_chat.id,
                document=db_file,
                filename=f"videobot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                caption=caption,
                parse_mode="HTML"
            )
        await status_msg.delete()
    except Exception as e:
        logger.exception("Backup error")
        await status_msg.edit_text(f"❌ Backup failed: {e}")


# ─── /restore ─────────────────────────────────────────────────

@admin_only
async def restore_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from database.db import DB_PATH, init_db
    import os
    import shutil

    reply = update.message.reply_to_message
    if not reply or not reply.document:
        await update.message.reply_text(
            "⚠️ <b>How to Restore:</b>\n\n"
            "1. Upload or forward your backup <code>.db</code> file here.\n"
            "2. Reply to that file with <code>/restore</code>.",
            parse_mode="HTML"
        )
        return

    doc = reply.document
    if not (doc.file_name or "").endswith(".db"):
        await update.message.reply_text("❌ The attached file must be an SQLite database ending in <code>.db</code>.", parse_mode="HTML")
        return

    status_msg = await update.message.reply_text("⏳ Downloading and verifying backup file…")
    temp_path = f"{DB_PATH}.restore_temp"
    backup_old = f"{DB_PATH}.bak"
    try:
        tg_file = await ctx.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(custom_path=temp_path)

        # Validate SQLite header magic bytes
        with open(temp_path, "rb") as f:
            header = f.read(16)
        if not header.startswith(b"SQLite format 3\x00"):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            await status_msg.edit_text("❌ Invalid database file! Header does not match SQLite format 3.")
            return

        # Backup current db before overwrite
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_old)

        # Replace active db
        shutil.move(temp_path, DB_PATH)

        # Re-initialize schema and indexes
        await init_db()
        stats = await get_stats()

        await status_msg.edit_text(
            "✅ <b>Database Restored Successfully!</b>\n\n"
            f"👥 Restored Users: <b>{stats['total_users']}</b>\n"
            f"🌟 Restored Premium: <b>{stats['premium_users']}</b>\n"
            f"📥 Total Downloads: <b>{stats['total_downloads']}</b>\n\n"
            "All user records and quotas are now active! 🚀",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("Restore error")
        if os.path.exists(backup_old) and not os.path.exists(DB_PATH):
            shutil.copy2(backup_old, DB_PATH)
        await status_msg.edit_text(f"❌ Restore failed: {e}")


# ─── /setchannel & /channel ───────────────────────────────────

@admin_only
async def setchannel_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set or remove the force-subscription channel.
    Usage:
      /setchannel @YourChannel
      /setchannel -1001234567890
      /setchannel off  (disables FSUB)
    """
    args = ctx.args
    if not args:
        from utils.fsub import get_required_channel
        current = await get_required_channel()
        msg = (
            f"📢 <b>Current Force-Subscribe Channel:</b> <code>{current or 'Disabled'}</code>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/setchannel @YourChannel</code> — Require users to join this channel\n"
            "• <code>/setchannel -1001234567890</code> — Support private channels via ID\n"
            "• <code>/setchannel off</code> — Disable force-subscription\n\n"
            "⚠️ <i>Make sure to add this bot as an Admin in your channel!</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    arg = args[0].strip()
    if arg.lower() in ("off", "none", "disable", "disabled", "0"):
        await set_setting("fsub_channel", "")
        await update.message.reply_text(
            "✅ <b>Force-Subscription Disabled!</b>\n\nUsers can now use the bot without subscribing to any channel.",
            parse_mode="HTML"
        )
        return

    # Normalize link/username/ID (e.g. https://t.me/Channel, t.me/Channel, @Channel, -100...)
    clean_arg = arg
    for prefix in ("@https://t.me/", "@http://t.me/", "https://t.me/", "http://t.me/", "t.me/"):
        if clean_arg.startswith(prefix):
            clean_arg = clean_arg[len(prefix):]
            break
    clean_arg = clean_arg.strip().rstrip("/")

    if clean_arg.startswith("-"):
        channel = clean_arg
    else:
        channel = clean_arg if clean_arg.startswith("@") else f"@{clean_arg}"

    # Verify if bot can access the channel and is admin
    status_note = ""
    try:
        bot_info = await ctx.bot.get_me()
        chat = await ctx.bot.get_chat(channel)
        member = await ctx.bot.get_chat_member(chat.id, bot_info.id)
        if member.status not in ("administrator", "creator"):
            status_note = (
                f"\n\n⚠️ <b>Warning:</b> Bot found channel <i>{chat.title}</i>, but the bot is <b>NOT an Administrator</b>.\n"
                f"👉 Please promote @{bot_info.username} to <b>Admin</b> in the channel so it can check user subscriptions!"
            )
        else:
            status_note = f"\n\n✅ <b>Verified:</b> Bot is an Admin in <i>{chat.title}</i>."
    except Exception as e:
        logger.warning(f"Could not verify bot admin status in {channel}: {e}")
        status_note = (
            f"\n\n⚠️ <i>Note: Could not check bot status in channel ({e}).</i>\n"
            "Please ensure the bot has been added as an <b>Admin</b> in the channel."
        )

    await set_setting("fsub_channel", channel)
    await update.message.reply_text(
        f"✅ <b>Force-Subscribe Channel Saved!</b>\n\n"
        f"Channel: <code>{channel}</code>"
        f"{status_note}\n\n"
        "Users must now join this channel to use the bot.",
        parse_mode="HTML"
    )


@admin_only
async def channel_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """View the currently active force-subscription channel."""
    from utils.fsub import get_required_channel
    channel = await get_required_channel()
    if not channel:
        await update.message.reply_text(
            "📢 Force-Subscribe is currently <b>Disabled</b>.\n\n"
            "Use <code>/setchannel @YourChannel</code> to enable it.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"📢 Active Force-Subscribe Channel: <code>{channel}</code>\n\n"
            "• To change: <code>/setchannel @NewChannel</code>\n"
            "• To disable: <code>/setchannel off</code>",
            parse_mode="HTML"
        )


# ─── /autodelete ──────────────────────────────────────────────

@admin_only
async def autodelete_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set or inspect the auto-delete timer for sent videos and cards."""
    args = ctx.args
    if not args:
        current = await get_auto_delete_minutes()
        timer_str = f"{current} minutes" if current > 0 else "Disabled"
        msg = (
            f"⏳ <b>Auto-Delete Timer:</b> <code>{timer_str}</code>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/autodelete 1</code> — Set to 1 minute (fast test!)\n"
            "• <code>/autodelete 30</code> — Standard 30-minute timer\n"
            "• <code>/autodelete off</code> — Keep videos permanently\n\n"
            "ℹ️ <i>Telegram limitation: Bots can auto-delete the videos, cards, and buttons THEY send. Telegram does not allow bots to delete user-typed messages in 1-on-1 private chats.</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    val = args[0].strip().lower()
    if val in ("off", "none", "disable", "disabled", "0"):
        await set_setting("auto_delete_minutes", "0")
        await update.message.reply_text("✅ <b>Auto-Delete Disabled!</b> Videos will no longer be deleted automatically.", parse_mode="HTML")
        return

    if not val.isdigit() or int(val) < 1:
        await update.message.reply_text("❌ Please specify minutes as a positive number (e.g. <code>/autodelete 1</code> or <code>/autodelete 30</code>).", parse_mode="HTML")
        return

    mins = int(val)
    await set_setting("auto_delete_minutes", str(mins))
    await update.message.reply_text(
        f"✅ <b>Auto-Delete Timer Updated!</b>\n\n"
        f"Videos and cards will now automatically disappear after <b>{mins} minute{'s' if mins > 1 else ''}</b>.",
        parse_mode="HTML"
    )


# ─── /setad ───────────────────────────────────────────────────

@admin_only
async def setad_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Set or remove the Monetag ad tag / zone ID for the Web App."""
    args = ctx.args
    if not args:
        current = await get_setting("monetag_tag")
        msg = (
            f"📢 <b>Current Monetag Ad Tag:</b> <code>{current or 'Default Sponsor Card'}</code>\n\n"
            "<b>Usage:</b>\n"
            "• <code>/setad YOUR_MONETAG_TAG_OR_ZONE_ID</code> — Enable live Monetag ads\n"
            "• <code>/setad off</code> — Use default sponsor card\n\n"
            "ℹ️ <i>Monetag ads are shown to free users during the 10-second download countdown. VIP users bypass them automatically.</i>"
        )
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    val = " ".join(args).strip()
    if val.lower() in ("off", "none", "disable", "disabled", "0"):
        await set_setting("monetag_tag", "")
        await update.message.reply_text("✅ <b>Monetag Live Ads Disabled!</b> Using default sponsor card.", parse_mode="HTML")
        return

    await set_setting("monetag_tag", val)
    await update.message.reply_text(
        f"✅ <b>Monetag Ad Tag Saved!</b>\n\n"
        f"Tag: <code>{val}</code>\n\n"
        "Free users will now see live Monetag ads in the Mini App during the 10-second download countdown.",
        parse_mode="HTML"
    )


# ─── Helper ───────────────────────────────────────────────────

async def _resolve_target(target: str) -> dict | None:
    """Resolve username or user_id string to user dict."""
    if target.isdigit():
        return await get_user(int(target))
    return await search_user(target)
