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

# Concurrency limits: max 3 simultaneous downloads system-wide, max 1 per user
_system_download_semaphore = asyncio.Semaphore(3)
_user_locks: dict[int, asyncio.Lock] = {}

def _get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]

from database.models import (
    get_or_create_user, get_user, can_use,
    decrement_free_uses, increment_total_uses, log_download,
    schedule_message_deletion, get_cached_video, save_cached_video,
    get_auto_delete_minutes,
)
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

    # Check if user is submitting UPI UTR payment reference
    if ctx.user_data.get("awaiting_utr"):
        from handlers.payment import handle_utr_submission
        await handle_utr_submission(update, ctx)
        return

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

    from utils.fsub import is_subscribed, get_fsub_keyboard, get_fsub_message
    if not await is_subscribed(ctx.bot, tg_user.id):
        await msg.reply_text(
            await get_fsub_message(),
            parse_mode="HTML",
            reply_markup=await get_fsub_keyboard(),
        )
        return

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


    # Store in session
    url_hash = store_session(url, info)

    user = await get_user(tg_user.id)
    text = video_info_message(info, user)
    web_url = info.get("final_url") or info.get("direct_url") or url
    keyboard = video_action_keyboard(info["formats"], url_hash, web_url=web_url, original_url=url)

    # Send thumbnail if available
    photo_sent = False
    card_msg = None
    if info.get("thumbnail"):
        try:
            card_msg = await ctx.bot.send_photo(
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
        except Exception as e:
            logger.warning(f"Could not send thumbnail photo: {e}")
            photo_sent = False

    if not photo_sent:
        try:
            card_msg = await fetching_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        except Exception:
            card_msg = await msg.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

    # Automatically schedule the unlocked card for deletion
    auto_del_mins = await get_auto_delete_minutes()
    if card_msg and auto_del_mins > 0:
        try:
            await schedule_message_deletion(msg.chat_id, card_msg.message_id, auto_del_mins * 60)
        except Exception as de:
            logger.warning(f"Could not schedule card deletion: {de}")


# ─── Callback Query Handler ───────────────────────────────────

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "cancel":
        await query.message.delete()
        return

    if data == "refresh_refer":
        from handlers.start import refresh_refer_callback
        await refresh_refer_callback(update, ctx)
        return

    if data == "check_fsub":
        from utils.fsub import is_subscribed
        joined = await is_subscribed(ctx.bot, query.from_user.id)
        if joined:
            await query.answer("✅ Verified! Welcome aboard.", show_alert=True)
            try:
                await query.message.delete()
            except Exception:
                pass
            await ctx.bot.send_message(
                chat_id=query.message.chat_id,
                text="🎉 <b>Membership verified!</b>\nSend any TeraBox or DiskWala link to start streaming or downloading.",
                parse_mode="HTML"
            )
        else:
            await query.answer("❌ You haven't joined the channel yet! Please join to continue.", show_alert=True)
        return

    if data == "goto_premium":
        from handlers.payment import premium_command
        await premium_command(update, ctx)
        return

    if data == "pay_upi_qr":
        from handlers.payment import pay_upi_qr_callback
        await pay_upi_qr_callback(update, ctx)
        return

    if data == "submit_utr":
        from handlers.payment import submit_utr_callback
        await submit_utr_callback(update, ctx)
        return

    if data.startswith("approve_vip:"):
        from handlers.payment import approve_vip_callback
        await approve_vip_callback(update, ctx)
        return

    if data.startswith("reject_vip:"):
        from handlers.payment import reject_vip_callback
        await reject_vip_callback(update, ctx)
        return

    if data == "verify_payment":
        await query.message.reply_text(
            "✅ <b>Payment Status Check</b>\n\n"
            "• If paid via <b>Razorpay</b>, activation is automated within 2 minutes.\n"
            "• If paid via <b>UPI QR Code</b>, tap <b>✍️ Submit UTR / Reference No.</b> to submit your receipt for instant admin approval.\n\n"
            "If your VIP is not active after 10 minutes, contact @admin for immediate help.",
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
    if info.get("platform") == "diskwala" or info.get("is_app_only"):
        from config import TERABOX_WEBAPP_URL
        from urllib.parse import quote
        from telegram import WebAppInfo
        player_link = f"{TERABOX_WEBAPP_URL}?url={quote(url, safe='')}" if TERABOX_WEBAPP_URL.startswith("https://") else ""
        kb_rows = []
        if player_link:
            kb_rows.append([InlineKeyboardButton("🌐 Watch Online", web_app=WebAppInfo(url=player_link))])
        await query.answer("DiskWala videos stream online via Watch Online!", show_alert=True)
        await query.message.reply_text(
            "💾 <b>DiskWala Cloud Video</b>\n\n"
            "DiskWala does not allow direct file downloads into Telegram chat.\n\n"
            "👉 Tap <b>🌐 Watch Online</b> below to stream:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None
        )
        return

    fmt = info["formats"][min(fmt_idx, len(info["formats"]) - 1)]
    title = info.get("title") or "Video"
    esc_title = html.escape(title[:60])
    file_key = info.get("file_key") or get_canonical_file_key(url)
    auto_del_mins = await get_auto_delete_minutes()

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
                if auto_del_mins > 0:
                    auto_del_note = f"\n⏳ <i>This video will auto-delete in {auto_del_mins} minutes.</i>\n"

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
                if auto_del_mins > 0 and sent_msg:
                    delay_sec = auto_del_mins * 60
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

    # ── Concurrency check: 1 per user, max 3 system-wide ──
    user_lock = _get_user_lock(tg_user.id)
    if user_lock.locked():
        await ctx.bot.send_message(
            chat_id=chat_id,
            text="⏳ <b>A video is already processing for you.</b>\nPlease wait for it to finish.",
            parse_mode="HTML"
        )
        return

    await user_lock.acquire()
    await _system_download_semaphore.acquire()
    acquired_locks = True

    filepath = None
    progress_msg = None
    try:
        # Send progress message
        action_label = "download" if action == "download" else "stream"
        progress_msg = await ctx.bot.send_message(
            chat_id=chat_id,
            text=f"⬇️ <b>Starting {action_label}…</b>\n\n📹 <i>{esc_title}</i>",
            parse_mode="HTML"
        )
        progress = ProgressBar(progress_msg, title)
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
                if auto_del_mins > 0:
                    auto_del_note = f"\n⏳ <i>This video will auto-delete in {auto_del_mins} minutes.</i>\n"

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
                if auto_del_mins > 0 and sent_msg:
                    delay_sec = auto_del_mins * 60
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
            # Immediately delete temp file on server to prevent filling container storage
            try:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                    filepath = None
            except Exception:
                pass

            from utils.keyboards import large_file_keyboard
            stream_direct = direct_url or fmt.get("direct_url") or info.get("final_url") or ""
            large_kb = large_file_keyboard(
                original_url=url,
                direct_url=stream_direct,
                title=title,
                file_size_mb=file_size_mb,
            )

            large_text = (
                f"⚡ <b>Large File Ready: {file_size_mb:.1f} MB</b>\n\n"
                f"📹 <b>Title:</b> <code>{esc_title}</code>\n"
                f"🎚 <b>Quality:</b> <b>{html.escape(fmt['label'])}</b>\n"
                f"📦 <b>Size:</b> <b>{file_size_mb:.1f} MB</b>\n\n"
                "ℹ️ <i>Telegram Bot API limits direct in-chat uploads to 50 MB, but you can stream or download this entire file at full speed below:</i>"
            )

            await progress_msg.edit_text(
                large_text,
                parse_mode="HTML",
                reply_markup=large_kb,
            )

            # Schedule auto-delete
            if auto_del_mins > 0 and progress_msg:
                delay_sec = auto_del_mins * 60
                await schedule_message_deletion(chat_id, progress_msg.message_id, delay_sec)

            # Decrement quota & log
            db_user = await get_user(tg_user.id)
            if not db_user["is_premium"]:
                await decrement_free_uses(tg_user.id)
            await increment_total_uses(tg_user.id)
            await log_download(tg_user.id, url, title, fmt["label"], "web_download", file_size)
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
        if auto_del_mins > 0:
            auto_del_note = f"\n⏳ <i>This video will auto-delete in {auto_del_mins} minutes.</i>\n"

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

        # Schedule auto-delete after auto_del_mins
        if auto_del_mins > 0 and sent_msg:
            delay_sec = auto_del_mins * 60
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
                        "Upgrade to Premium for ₹99/month (30 Days) — use /premium"
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
        if progress_msg:
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
        if acquired_locks:
            _system_download_semaphore.release()
            user_lock.release()


# ─── Payment URL helper ───────────────────────────────────────

async def _get_payment_url(user_id: int, full_name: str) -> str:
    try:
        from handlers.payment import create_payment_link
        return await create_payment_link(user_id, full_name)
    except Exception:
        return "https://razorpay.com"
