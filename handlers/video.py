"""Core video handler — link detection, info display, play/download."""
from __future__ import annotations

import os
import html
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

logger = logging.getLogger(__name__)

from database.models import (
    get_or_create_user, get_user, can_use,
    decrement_free_uses, increment_total_uses, log_download,
    schedule_message_deletion, get_cached_video, save_cached_video,
)
from config import AUTO_DELETE_MINUTES
from utils.downloader import (
    detect_platform, extract_url, get_video_info, download_video,
    get_canonical_file_key,
)
from utils.progress import ProgressBar
from utils.keyboards import (
    video_action_keyboard, selected_quality_keyboard,
    video_info_message, quota_exceeded_message,
)
from utils.sessions import store_session, get_session


# ─── Link Message Handler ─────────────────────────────────────

async def link_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Called when user sends a message. Check if it has a valid link."""
    msg = update.message
    text = msg.text or ""

    url = extract_url(text)
    if not url:
        return  # Not a URL, ignore silently

    platform = detect_platform(url)
    if not platform:
        await msg.reply_text(
            "⚠️ <b>I only support Terabox and DiskWala links.</b>\n"
            "Please send a valid link.",
            parse_mode="HTML"
        )
        return

    tg_user = update.effective_user
    user = await get_or_create_user(
        tg_user.id, tg_user.username or "", tg_user.full_name
    )

    # Check quota
    allowed, reason = await can_use(tg_user.id)
    if not allowed:
        if reason == "quota_exceeded":
            # Generate payment link and show upgrade prompt
            payment_url = await _get_payment_url(tg_user.id, tg_user.full_name)
            from utils.keyboards import buy_premium_keyboard
            await msg.reply_text(
                quota_exceeded_message(),
                parse_mode="HTML",
                reply_markup=buy_premium_keyboard(payment_url),
            )
        else:
            await msg.reply_text(f"⛔ {reason}")
        return

    # Fetch video info
    fetching_msg = await msg.reply_text(
        f"🔍 <b>Fetching video info…</b>\n<code>{html.escape(url[:60])}…</code>",
        parse_mode="HTML"
    )
    await ctx.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)

    try:
        info = await get_video_info(url)
    except Exception as e:
        await fetching_msg.edit_text(
            f"❌ <b>Failed to fetch video info.</b>\n\n"
            f"Error: <code>{html.escape(str(e))}</code>\n\n"
            "Make sure the link is valid and not expired.",
            parse_mode="HTML"
        )
        return

    if info.get("platform") == "diskwala":
        app_url = info.get("app_url") or url
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Open in DiskWala App", url=app_url)],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
        diskwala_text = (
            "💾 <b>DiskWala Link Detected</b>\n\n"
            f"📹 <b>File:</b> <code>{html.escape(info.get('title', 'DiskWala Video'))}</code>\n"
            f"🔗 <b>URL:</b> <code>{html.escape(url)}</code>\n\n"
            "⚠️ <b>Platform Notice:</b> DiskWala uses device hardware encryption and restricts video playback exclusively to their official mobile application.\n\n"
            "📲 <b>To watch:</b> Tap below to open directly in the <b>DiskWala App</b>:"
        )
        try:
            await fetching_msg.edit_text(diskwala_text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await msg.reply_text(diskwala_text, parse_mode="HTML", reply_markup=keyboard)
        return

    # Store in session
    url_hash = store_session(url, info)

    user = await get_user(tg_user.id)
    text = video_info_message(info, user)
    web_url = info.get("final_url") or info.get("direct_url") or url
    keyboard = video_action_keyboard(info["formats"], url_hash, web_url=web_url, original_url=url)

    # Send thumbnail if available
    photo_sent = False
    if info.get("thumbnail"):
        try:
            await ctx.bot.send_photo(
                chat_id=msg.chat_id,
                photo=info["thumbnail"],
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            photo_sent = True
            try:
                await fetching_msg.delete()
            except Exception:
                pass
            return
        except Exception as e:
            logger.warning(f"Could not send thumbnail photo: {e}")
            photo_sent = False

    if not photo_sent:
        try:
            await fetching_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            await msg.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


# ─── Callback Query Handler ───────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "cancel":
        await query.message.delete()
        return

    if data == "goto_premium":
        from handlers.payment import premium_command
        await premium_command(update, ctx)
        return

    if data == "verify_payment":
        await query.message.reply_text(
            "✅ Please allow up to <b>5 minutes</b> for payment verification.\n"
            "If not activated after 10 minutes, contact @admin.",
            parse_mode="HTML"
        )
        return

    if data.startswith("localplayer:"):
        url_hash = data.split(":")[1]
        session = get_session(url_hash)
        orig_url = session["url"] if session else ""
        from urllib.parse import quote
        from config import PORT
        player_link = f"http://localhost:{PORT}/player?url={quote(orig_url, safe='')}" if orig_url else f"http://localhost:{PORT}/player"
        await query.message.reply_text(
            f"💻 <b>Play in your PC Browser:</b>\n\n"
            f"Open this link in Chrome or Edge on your PC:\n"
            f"👉 <a href=\"{player_link}\">{player_link}</a>\n\n"
            f"✨ <i>Plays the full video without 1-second cuts or ads!</i>",
            parse_mode="HTML"
        )
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    action, url_hash, fmt_idx_str = parts[0], parts[1], parts[2]
    fmt_idx = int(fmt_idx_str)

    session = get_session(url_hash)
    if not session:
        await query.message.reply_text(
            "⚠️ Session expired. Please send the link again."
        )
        return

    info = session["info"]
    url = session["url"]
    web_url = info.get("final_url") or info.get("direct_url") or url

    if action == "quality":
        fmt = info["formats"][fmt_idx]
        kb = selected_quality_keyboard(url_hash, fmt_idx, fmt["label"], web_url=web_url, original_url=url)
        await query.message.edit_reply_markup(reply_markup=kb)
        return

    if action == "back":
        kb = video_action_keyboard(info["formats"], url_hash, web_url=web_url, original_url=url)
        await query.message.edit_reply_markup(reply_markup=kb)
        return

    if action in ("play", "download"):
        await _handle_download(query, ctx, url, info, fmt_idx, action)


# ─── Download & Send ──────────────────────────────────────────

async def _handle_download(query, ctx, url: str, info: dict,
                            fmt_idx: int, action: str):
    tg_user = query.from_user
    chat_id = query.message.chat_id

    # Re-check quota
    allowed, reason = await can_use(tg_user.id)
    if not allowed:
        if reason == "quota_exceeded":
            payment_url = await _get_payment_url(tg_user.id, tg_user.full_name)
            from utils.keyboards import buy_premium_keyboard
            await query.message.reply_text(
                quota_exceeded_message(),
                parse_mode="HTML",
                reply_markup=buy_premium_keyboard(payment_url),
            )
        else:
            await query.message.reply_text(f"⛔ {reason}")
        return

    fmt = info["formats"][min(fmt_idx, len(info["formats"]) - 1)]
    title = info.get("title") or "Video"
    esc_title = html.escape(title[:60])
    file_key = info.get("file_key") or get_canonical_file_key(url)

    # ── 1. Check Instant Telegram file_id Cache (< 0.5s) ──
    if action == "play":
        cached = await get_cached_video(file_key)
        if cached and cached.get("file_id"):
            try:
                logger.info(f"⚡ INSTANT CACHE HIT for {file_key}! Sending file_id...")
                bot_uname = ctx.bot.username
                if not bot_uname:
                    try:
                        me = await ctx.bot.get_me()
                        bot_uname = me.username
                    except Exception:
                        bot_uname = "Tera_Player_Bot"

                auto_del_note = ""
                if AUTO_DELETE_MINUTES > 0:
                    auto_del_note = f"\n⏳ <i>This video will auto-delete in {AUTO_DELETE_MINUTES} minutes.</i>\n"

                cached_size_mb = (cached.get("file_size") or 0) / (1024 ** 2)
                size_str = f"📦 Size: <b>{cached_size_mb:.1f} MB</b>\n" if cached_size_mb > 0 else ""
                caption = (
                    f"🎬 <b>{esc_title}</b>\n"
                    f"🎚 Quality: <b>{html.escape(cached.get('quality') or fmt['label'])}</b> <i>(⚡ Instant)</i>\n"
                    f"{size_str}"
                    f"{auto_del_note}\n"
                    f"Powered by @{html.escape(bot_uname or 'Tera_Player_Bot')}"
                )

                sent_msg = await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=cached["file_id"],
                    caption=caption,
                    parse_mode="HTML",
                    supports_streaming=True,
                )

                # Schedule auto-delete
                if AUTO_DELETE_MINUTES > 0 and sent_msg:
                    delay_sec = AUTO_DELETE_MINUTES * 60
                    await schedule_message_deletion(chat_id, sent_msg.message_id, delay_sec)
                    if query and getattr(query, "message", None):
                        await schedule_message_deletion(chat_id, query.message.message_id, delay_sec)

                # Decrement quota & log
                db_user = await get_user(tg_user.id)
                if not db_user["is_premium"]:
                    await decrement_free_uses(tg_user.id)
                await increment_total_uses(tg_user.id)
                await log_download(tg_user.id, url, title, fmt["label"], action, cached.get("file_size") or 0)
                return
            except Exception as cache_err:
                logger.warning(f"Cache send failed ({cache_err}), falling back to direct stream...")

    # Send progress message
    action_label = "download" if action == "download" else "stream"
    progress_msg = await ctx.bot.send_message(
        chat_id=chat_id,
        text=f"⬇️ <b>Starting {action_label}…</b>\n\n📹 <i>{esc_title}</i>",
        parse_mode="HTML"
    )
    progress = ProgressBar(progress_msg, title)

    filepath = None
    try:
        await ctx.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)

        direct_url = fmt.get("direct_url")

        # ── 2. Attempt Direct Telegram Cloud Fetch (1-2s) ──
        if direct_url and action == "play" and not any(k in direct_url for k in ("m3u8", "share/streaming")):
            try:
                await progress_msg.edit_text("⚡ <b>Fetching from high-speed cloud…</b>", parse_mode="HTML")
                bot_uname = ctx.bot.username
                if not bot_uname:
                    try:
                        me = await ctx.bot.get_me()
                        bot_uname = me.username
                    except Exception:
                        bot_uname = "Tera_Player_Bot"

                auto_del_note = ""
                if AUTO_DELETE_MINUTES > 0:
                    auto_del_note = f"\n⏳ <i>This video will auto-delete in {AUTO_DELETE_MINUTES} minutes.</i>\n"

                caption = (
                    f"🎬 <b>{esc_title}</b>\n"
                    f"🎚 Quality: <b>{html.escape(fmt['label'])}</b>\n"
                    f"{auto_del_note}\n"
                    f"Powered by @{html.escape(bot_uname or 'Tera_Player_Bot')}"
                )

                sent_msg = await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=direct_url,
                    caption=caption,
                    parse_mode="HTML",
                    supports_streaming=True,
                    read_timeout=180,
                    write_timeout=180,
                    connect_timeout=60,
                )
                logger.info(f"Direct cloud fetch succeeded for {url}! 🚀")

                # Cache file_id for instant zero-download delivery next time!
                if sent_msg and sent_msg.video:
                    await save_cached_video(
                        file_key=file_key,
                        file_id=sent_msg.video.file_id,
                        title=title,
                        file_size=sent_msg.video.file_size or 0,
                        duration=sent_msg.video.duration or 0,
                        quality=fmt["label"],
                    )

                await progress_msg.delete()

                # Schedule auto-delete
                if AUTO_DELETE_MINUTES > 0 and sent_msg:
                    delay_sec = AUTO_DELETE_MINUTES * 60
                    await schedule_message_deletion(chat_id, sent_msg.message_id, delay_sec)
                    if query and getattr(query, "message", None):
                        await schedule_message_deletion(chat_id, query.message.message_id, delay_sec)

                # Decrement quota & log
                db_user = await get_user(tg_user.id)
                if not db_user["is_premium"]:
                    await decrement_free_uses(tg_user.id)
                await increment_total_uses(tg_user.id)
                await log_download(tg_user.id, url, title, fmt["label"], action, 0)
                return
            except Exception as cloud_err:
                logger.info(f"Direct cloud fetch skipped ({cloud_err}), downloading via accelerated stream buffer...")

        # ── 3. High-Speed Accelerated Local Stream Download ──
        filepath = await download_video(
            url=url,
            format_id=fmt["format_id"],
            progress_cb=progress.update,
            direct_url=direct_url,
        )

        file_size = os.path.getsize(filepath)
        file_size_mb = file_size / (1024 ** 2)

        await progress.done(file_size_mb)

        # Check Telegram 50MB limit
        if file_size_mb > 50:
            watch_url = html.escape(info.get("final_url") or url)
            await progress_msg.edit_text(
                f"⚠️ <b>File too large for Telegram!</b>\n\n"
                f"📦 Size: <b>{file_size_mb:.1f} MB</b> (limit: 50 MB)\n\n"
                f"🌐 You can watch it directly in browser:\n"
                f"<a href=\"{watch_url}\">👉 Tap here to watch online</a>\n\n"
                f"Or try selecting a lower quality resolution.",
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
            return

        await progress.sending()

        bot_uname = ctx.bot.username
        if not bot_uname:
            try:
                me = await ctx.bot.get_me()
                bot_uname = me.username
            except Exception:
                bot_uname = "Tera_Player_Bot"

        auto_del_note = ""
        if AUTO_DELETE_MINUTES > 0:
            auto_del_note = f"\n⏳ <i>This video will auto-delete in {AUTO_DELETE_MINUTES} minutes.</i>\n"

        caption = (
            f"🎬 <b>{esc_title}</b>\n"
            f"🎚 Quality: <b>{html.escape(fmt['label'])}</b>\n"
            f"📦 Size: <b>{file_size_mb:.1f} MB</b>\n"
            f"{auto_del_note}\n"
            f"Powered by @{html.escape(bot_uname or 'Tera_Player_Bot')}"
        )

        sent_msg = None
        if action == "download":
            # Send as downloadable document file
            with open(filepath, "rb") as vf:
                sent_msg = await ctx.bot.send_document(
                    chat_id=chat_id,
                    document=vf,
                    filename=os.path.basename(filepath),
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60,
                )
        else:
            # Action is 'play' -> Send as playable streaming video
            with open(filepath, "rb") as vf:
                sent_msg = await ctx.bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    caption=caption,
                    parse_mode="HTML",
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60,
                )

        await progress_msg.delete()

        # Cache file_id for instant delivery next time
        if sent_msg and getattr(sent_msg, "video", None):
            try:
                await save_cached_video(
                    file_key=file_key,
                    file_id=sent_msg.video.file_id,
                    title=title,
                    file_size=file_size,
                    duration=sent_msg.video.duration or 0,
                    quality=fmt["label"],
                )
                logger.info(f"Cached file_id for {file_key} ✅")
            except Exception as ce:
                logger.warning(f"Could not cache file_id: {ce}")

        # Schedule auto-delete after AUTO_DELETE_MINUTES
        if AUTO_DELETE_MINUTES > 0 and sent_msg:
            delay_sec = AUTO_DELETE_MINUTES * 60
            try:
                await schedule_message_deletion(chat_id, sent_msg.message_id, delay_sec)
                if query and getattr(query, "message", None):
                    await schedule_message_deletion(chat_id, query.message.message_id, delay_sec)
            except Exception as se:
                logger.warning(f"Could not schedule deletion: {se}")

        # Decrement quota & log
        db_user = await get_user(tg_user.id)
        if not db_user["is_premium"]:
            await decrement_free_uses(tg_user.id)
        await increment_total_uses(tg_user.id)
        await log_download(
            tg_user.id, url, title, fmt["label"], action, file_size
        )

        # Show remaining quota if on free tier
        if not db_user["is_premium"]:
            updated = await get_user(tg_user.id)
            rem = updated["free_uses"]
            if rem <= 2:
                await ctx.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⚠️ <b>Only {rem} free use(s) remaining!</b>\n"
                        "Upgrade to Premium for ₹99 lifetime — use /premium"
                    ),
                    parse_mode="HTML"
                )

    except Exception as e:
        logger.exception(f"Operation failed for {url}: {e}")
        err_msg = str(e)
        if any(k in err_msg.lower() for k in ("timeout", "timed out", "readtimeout")):
            user_err = (
                "⏱ <b>Upload Timed Out</b>\n\n"
                "The video upload took too long due to network speed.\n"
                "Please try again or select a lower resolution."
            )
        else:
            user_err = f"❌ <b>Operation failed.</b>\n\nError: <code>{html.escape(err_msg[:200])}</code>"
        try:
            await progress_msg.edit_text(user_err, parse_mode="HTML")
        except Exception:
            pass
    finally:
        # Clean up local file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


# ─── Payment URL helper ───────────────────────────────────────

async def _get_payment_url(user_id: int, full_name: str) -> str:
    try:
        from handlers.payment import create_payment_link
        return await create_payment_link(user_id, full_name)
    except Exception:
        return "https://razorpay.com"
