import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# ─── Razorpay ────────────────────────────────────────────────
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ─── App Settings ────────────────────────────────────────────
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")      # e.g. https://your-app.railway.app
PORT = int(os.getenv("PORT", 8080))
FREE_QUOTA = 5
PREMIUM_PRICE_PAISE = 9900                       # ₹99 in paise
PREMIUM_PRICE_INR = 99
DOWNLOAD_DIR = "downloads"
MAX_FILE_SIZE_MB = 50                            # Telegram Bot API limit
AUTO_DELETE_MINUTES = int(os.getenv("AUTO_DELETE_MINUTES", "30"))  # Auto-disappear after 30 min
TERABOX_WEBAPP_URL = os.getenv(
    "TERABOX_WEBAPP_URL",
    f"{WEBHOOK_URL.rstrip('/')}/player" if WEBHOOK_URL else f"http://localhost:{PORT}/player"
)

# ─── Supported Domains ───────────────────────────────────────
TERABOX_DOMAINS = [
    "terabox.com", "1024tera.com", "1024terabox.com", "4funbox.com",
    "mirrobox.com", "nephobox.com", "freeterabox.com",
    "teraboxapp.com", "terabox.app", "terafileshare.com",
    "teraboxlink.com", "terasharelink.com", "terasharefile.com",
    "momerybox.com", "tibibox.com", "terabox.fun",
    "teraboxshare.com", "teraboxdrive.com", "terafiles.com",
    "dubox.com", "gibibox.com",
]

DISKWALA_DOMAINS = [
    "diskwala.com", "disk-wala.com",
]

BOT_NAME = "VideoBot Pro"

# ─── Allowed Streaming & Proxy Domains (SSRF Protection) ─────
ALLOWED_STREAM_DOMAINS = set(TERABOX_DOMAINS) | {
    "teraboxdl.site",
    "playterabox.com",
    "baidupcs.com",
}
