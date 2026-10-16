"""Razorpay and UPI QR Code payment handler."""
from __future__ import annotations

import os
import html
import logging
from urllib.parse import quote
import razorpay
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET,
    RAZORPAY_PAYMENT_URL, PREMIUM_PRICE_PAISE, PREMIUM_PRICE_INR, WEBHOOK_URL,
    UPI_ID, UPI_NAME, UPI_QR_IMAGE, ADMIN_IDS,
)
from database.models import (
    create_payment_record, grant_premium, get_user
)

logger = logging.getLogger(__name__)


# ─── Razorpay Client ─────────────────────────────────────────

def _razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# ─── Create Payment Link ─────────────────────────────────────

async def create_payment_link(user_id: int, full_name: str) -> str:
    """Creates a Razorpay Payment Link and returns the short URL."""
    if not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET):
        return RAZORPAY_PAYMENT_URL or "https://rzp.io/rzp/1tGAGsc"

    client = _razorpay_client()

    order = client.order.create({
        "amount": PREMIUM_PRICE_PAISE,
        "currency": "INR",
        "receipt": f"user_{user_id}",
        "notes": {"user_id": str(user_id), "plan": "monthly_30d"},
    })

    link_data = client.payment_link.create({
        "amount": PREMIUM_PRICE_PAISE,
        "currency": "INR",
        "description": "VideoBot Pro — Monthly Premium (30 Days)",
        "customer": {"name": full_name},
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {
            "user_id": str(user_id),
            "order_id": order["id"],
        },
        "callback_url": f"{WEBHOOK_URL}/payment/success?uid={user_id}",
        "callback_method": "get",
    })

    payment_link_id = link_data.get("id", "")
    short_url = link_data.get("short_url", link_data.get("url", ""))

    await create_payment_record(
        user_id=user_id,
        order_id=order["id"],
        payment_link_id=payment_link_id,
        amount_paise=PREMIUM_PRICE_PAISE,
    )

    return short_url or RAZORPAY_PAYMENT_URL or "https://rzp.io/rzp/1tGAGsc"


# ─── /premium Command ─────────────────────────────────────────

async def premium_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    msg = update.message or (update.callback_query.message if update.callback_query else None)

    # Check if already premium
    db_user = await get_user(tg_user.id)
    if db_user and db_user["is_premium"]:
        reply_txt = (
            "🌟 <b>You already have Premium access!</b>\n\n"
            "Enjoy unlimited downloads & streaming with zero ads. 🎉"
        )
        if update.callback_query:
            await update.callback_query.message.reply_text(reply_txt, parse_mode="HTML")
        else:
            await msg.reply_text(reply_txt, parse_mode="HTML")
        return

    payment_url = RAZORPAY_PAYMENT_URL or "https://rzp.io/rzp/1tGAGsc"
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        try:
            payment_url = await create_payment_link(tg_user.id, tg_user.full_name)
        except Exception as e:
            logger.warning(f"Could not generate dynamic Razorpay link: {e}")

    text = (
        "💎 <b>VideoBot Pro — Monthly Premium (30 Days)</b>\n\n"
        f"💰 <b>Price:</b> <code>₹{PREMIUM_PRICE_INR} / Month</code>\n\n"
        "✨ <b>Premium Benefits:</b>\n"
        "• ✅ <b>Unlimited video plays & downloads</b> (No limits)\n"
        "• ✅ <b>Zero ads & zero countdown waits</b>\n"
        "• ✅ <b>Full 4K, 1080p, and 720p qualities</b>\n"
        "• ✅ <b>Both TeraBox & DiskWala supported</b>\n"
        "• ✅ <b>High-speed accelerated cloud streaming</b>\n"
        "• ⏳ <b>Validity:</b> 30 Days of uninterrupted access\n\n"
        "👇 <b>Choose your payment method below:</b>"
    )

    from utils.keyboards import buy_premium_keyboard
    kb = buy_premium_keyboard(payment_url)

    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass

    await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ─── UPI QR Code Handler ──────────────────────────────────────

async def pay_upi_qr_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_user = query.from_user

    upi_intent = f"upi://pay?pa={UPI_ID}&pn={quote(UPI_NAME)}&am={PREMIUM_PRICE_INR}&cu=INR&tn=VIP_{tg_user.id}"

    caption = (
        "📱 <b>Pay via UPI / QR Code (0% Extra Fee)</b>\n\n"
        f"💰 <b>Amount:</b> <code>₹{PREMIUM_PRICE_INR}</code> (Monthly VIP — 30 Days)\n"
        f"👤 <b>Receiver:</b> <code>{html.escape(UPI_NAME)}</code>\n"
        f"🆔 <b>UPI ID:</b> <code>{html.escape(UPI_ID)}</code>\n\n"
        "📲 <b>How to pay:</b>\n"
        "1. Scan the QR code above with <b>GPay, PhonePe, Paytm, or BHIM</b>.\n"
        "   <i>(Or tap '📲 Open in UPI App' below)</i>\n"
        f"2. Pay <b>₹{PREMIUM_PRICE_INR}</b>.\n"
        "3. Copy the <b>12-digit UTR / Reference Number</b> from your receipt.\n"
        "4. Tap <b>✍️ Submit UTR / Reference No.</b> below to submit!\n\n"
        "⚡ <i>Once verified, your VIP access is activated immediately!</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Open in UPI App", url=upi_intent)],
        [InlineKeyboardButton("✍️ Submit UTR / Reference No.", callback_data="submit_utr")],
        [InlineKeyboardButton("🔙 Back to Payment Options", callback_data="goto_premium")],
    ])

    qr_sent = False
    qr_path = UPI_QR_IMAGE if os.path.exists(UPI_QR_IMAGE) else os.path.join("web", "static", "upi_qr.jpg")
    if os.path.exists(qr_path):
        try:
            with open(qr_path, "rb") as f:
                await query.message.reply_photo(
                    photo=f,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            qr_sent = True
        except Exception as e:
            logger.warning(f"Could not send QR photo: {e}")

    if not qr_sent:
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={quote(upi_intent)}"
        try:
            await query.message.reply_photo(
                photo=qr_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception:
            await query.message.reply_text(caption, parse_mode="HTML", reply_markup=kb)


# ─── UTR Submission Handler ───────────────────────────────────

async def submit_utr_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ctx.user_data["awaiting_utr"] = True

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="goto_premium")]
    ])

    await query.message.reply_text(
        "✍️ <b>Submit Your Payment Reference (UTR)</b>\n\n"
        "Please reply directly to this message with:\n"
        "• Your <b>12-digit UPI UTR / Reference Number</b> (e.g. <code>428910294821</code>)\n"
        "• <i>OR send a screenshot of the payment receipt!</i>\n\n"
        "⏳ We will verify your transaction and activate your VIP status immediately.",
        parse_mode="HTML",
        reply_markup=kb
    )


async def handle_utr_submission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    ctx.user_data["awaiting_utr"] = False

    utr_text = msg.text or msg.caption or "Screenshot Provided"
    photo = msg.photo[-1] if msg.photo else None

    await msg.reply_text(
        "✅ <b>Payment Details Received!</b>\n\n"
        f"🧾 <b>Reference:</b> <code>{html.escape(utr_text[:40])}</code>\n"
        "⏳ <b>Status:</b> Sent to Admin for instant verification.\n\n"
        "Your <b>VIP Access (30 Days)</b> will be activated within a few minutes! 🚀",
        parse_mode="HTML"
    )

    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    clean_utr = "".join(c for c in utr_text if c.isalnum())[:16] or "SCREENSHOT"
    admin_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve VIP (30 Days)", callback_data=f"approve_vip:{user.id}:{clean_utr}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_vip:{user.id}:{clean_utr}")
        ]
    ])

    admin_text = (
        "🔔 <b>New UPI Payment Verification Request</b>\n\n"
        f"👤 <b>User:</b> {html.escape(user.full_name)} (@{user.username or 'NoUsername'})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        "💰 <b>Plan:</b> Monthly VIP (₹99 / 30 Days)\n"
        f"🧾 <b>UTR / Details:</b> <code>{html.escape(utr_text)}</code>\n"
        f"📅 <b>Time:</b> <code>{now_str}</code>"
    )

    for admin_id in ADMIN_IDS:
        try:
            if photo:
                await ctx.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo.file_id,
                    caption=admin_text,
                    parse_mode="HTML",
                    reply_markup=admin_kb
                )
            else:
                await ctx.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode="HTML",
                    reply_markup=admin_kb
                )
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id}: {e}")


# ─── Admin Approval & Rejection ───────────────────────────────

async def approve_vip_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return

    target_user_id = int(parts[1])
    utr = parts[2]

    await grant_premium(target_user_id, days=30)

    admin_name = html.escape(query.from_user.first_name)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    orig_text = query.message.caption or query.message.text or ""
    new_text = f"{orig_text}\n\n✅ <b>APPROVED by {admin_name}</b> — 30 Days VIP granted!"
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=new_text, parse_mode="HTML")
        else:
            await query.edit_message_text(text=new_text, parse_mode="HTML")
    except Exception:
        pass

    try:
        await ctx.bot.send_message(
            chat_id=target_user_id,
            text=(
                "🎉 <b>Payment Approved! Welcome to VIP!</b>\n\n"
                "🌟 Your <b>Monthly Premium (30 Days)</b> has been activated.\n"
                "🚀 Unlimited TeraBox & DiskWala downloads and streaming with zero forced ads or limits!\n\n"
                "Send any link to start enjoying VIP privileges. 🎬"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {target_user_id} of VIP approval: {e}")


async def reject_vip_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("⛔ Admin access only.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return

    target_user_id = int(parts[1])
    utr = parts[2]

    admin_name = html.escape(query.from_user.first_name)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    orig_text = query.message.caption or query.message.text or ""
    new_text = f"{orig_text}\n\n❌ <b>REJECTED by {admin_name}</b>"
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=new_text, parse_mode="HTML")
        else:
            await query.edit_message_text(text=new_text, parse_mode="HTML")
    except Exception:
        pass

    try:
        await ctx.bot.send_message(
            chat_id=target_user_id,
            text=(
                "⚠️ <b>Payment Verification Notice</b>\n\n"
                f"We could not verify your payment with reference <code>{html.escape(utr)}</code>.\n\n"
                "Please check your transaction receipt and try again via /premium, or contact support if you need assistance."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {target_user_id} of rejection: {e}")


# ─── Webhook Payment Verification ────────────────────────────

async def verify_razorpay_webhook(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook HMAC signature."""
    import hmac, hashlib
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def process_payment_webhook(payload: dict, bot) -> bool:
    """Handle payment.captured or payment_link.paid webhook events."""
    event = payload.get("event", "")

    if event == "payment_link.paid":
        entity = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
        notes = entity.get("notes", {})
        user_id = notes.get("user_id")
        order_id = notes.get("order_id")
        payment_id = (
            payload.get("payload", {})
            .get("payment", {})
            .get("entity", {})
            .get("id", "")
        )

    elif event == "payment.captured":
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        notes = entity.get("notes", {})
        user_id = notes.get("user_id")
        order_id = entity.get("order_id", "")
        payment_id = entity.get("id", "")

    else:
        return False

    if not user_id:
        return False

    user_id = int(user_id)

    from database.models import mark_payment_paid
    await mark_payment_paid(order_id, payment_id)
    await grant_premium(user_id, days=30)

    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 <b>Payment Successful! Welcome to Premium!</b>\n\n"
                "✅ Your account has been upgraded to <b>Monthly Premium (30 Days)</b>.\n"
                "🚀 Enjoy unlimited video downloads and streaming with zero ads!\n\n"
                "Send any TeraBox or DiskWala link to get started."
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass

    return True
