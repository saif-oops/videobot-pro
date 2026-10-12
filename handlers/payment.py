"""Razorpay payment handler."""
from __future__ import annotations

import razorpay
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET,
    PREMIUM_PRICE_PAISE, PREMIUM_PRICE_INR, WEBHOOK_URL,
)
from database.models import (
    create_payment_record, grant_premium, get_user, search_user
)


# ─── Razorpay Client ─────────────────────────────────────────

def _razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


# ─── Create Payment Link ─────────────────────────────────────

async def create_payment_link(user_id: int, full_name: str) -> str:
    """Creates a Razorpay Payment Link and returns the short URL."""
    client = _razorpay_client()

    # Create order first
    order = client.order.create({
        "amount": PREMIUM_PRICE_PAISE,
        "currency": "INR",
        "receipt": f"user_{user_id}",
        "notes": {"user_id": str(user_id), "plan": "monthly_30d"},
    })

    # Create payment link
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

    # Store in DB
    await create_payment_record(
        user_id=user_id,
        order_id=order["id"],
        payment_link_id=payment_link_id,
        amount_paise=PREMIUM_PRICE_PAISE,
    )

    return short_url


# ─── /premium Command ─────────────────────────────────────────

async def premium_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user

    # Check if already premium
    db_user = await get_user(tg_user.id)
    if db_user and db_user["is_premium"]:
        await (update.message or update.callback_query.message).reply_text(
            "🌟 You already have *Premium* access!\n\nEnjoy unlimited downloads. 🎉",
            parse_mode="Markdown",
        )
        return

    # Generate payment link
    wait_msg = await (update.message or update.callback_query.message).reply_text(
        "⏳ Generating your payment link…"
    )

    try:
        payment_url = await create_payment_link(tg_user.id, tg_user.full_name)
    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Failed to generate payment link.\nError: `{e}`\n"
            "Please try again later or contact support.",
            parse_mode="Markdown",
        )
        return

    text = (
        "💎 *VideoBot Pro — Monthly Premium*\n\n"
        f"💰 Price: *₹{PREMIUM_PRICE_INR} / Month (30 Days)*\n"
        "✅ Unlimited video plays & downloads\n"
        "✅ All quality options (4K → 360p)\n"
        "✅ TeraBox + DiskWala support\n"
        "✅ Priority high-speed cloud access\n"
        "⏳ Validity: *30 Days*\n\n"
        "🔒 Secure payment via *Razorpay (UPI, GPay, Paytm, Cards)*\n\n"
        "👇 Click the button below to pay:"
    )

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"💳 Pay ₹{PREMIUM_PRICE_INR} — 30 Days Access", url=payment_url),
    ], [
        InlineKeyboardButton("✅ I've Paid — Check Status", callback_data="verify_payment"),
    ]])

    await wait_msg.edit_text(text, parse_mode="Markdown", reply_markup=kb)


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
        return False  # unhandled event

    if not user_id:
        return False

    user_id = int(user_id)

    from database.models import mark_payment_paid
    await mark_payment_paid(order_id, payment_id)
    await grant_premium(user_id, days=30)

    # Notify user
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 *Payment Successful! Welcome to Premium!*\n\n"
                "✅ Your account has been upgraded to *Monthly Premium (30 Days)*.\n"
                "🚀 Enjoy unlimited video downloads and streaming!\n\n"
                "Send any TeraBox or DiskWala link to get started."
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    return True
