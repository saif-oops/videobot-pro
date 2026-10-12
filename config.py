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

# ─── Web App & Player Settings ───────────────────────────────
_raw_webapp = (
    os.getenv("WEB_APP_URL", "")
    or os.getenv("TERABOX_WEBAPP_URL", "")
    or os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    or os.getenv("RAILWAY_STATIC_URL", "")
).strip()

if not _raw_webapp and WEBHOOK_URL:
    _raw_webapp = f"{WEBHOOK_URL.rstrip('/')}/player"

# Auto-default to the live Railway domain if unset or on cloud
if not _raw_webapp:
    _raw_webapp = "https://videobot-pro.up.railway.app"

if _raw_webapp:
    if not _raw_webapp.startswith("http://") and not _raw_webapp.startswith("https://"):
        _raw_webapp = f"https://{_raw_webapp}"
    if not _raw_webapp.endswith("/player") and not _raw_webapp.endswith(".html"):
        TERABOX_WEBAPP_URL = f"{_raw_webapp.rstrip('/')}/player"
    else:
        TERABOX_WEBAPP_URL = _raw_webapp
else:
    TERABOX_WEBAPP_URL = "https://videobot-pro.up.railway.app/player"

# ─── Force-Subscribe (FSUB) ──────────────────────────────────
FSUB_CHANNEL = os.getenv("FSUB_CHANNEL", "").strip()          # e.g. @MyChannel or channel ID
FSUB_CHANNEL_URL = os.getenv("FSUB_CHANNEL_URL", "").strip()  # e.g. https://t.me/MyChannel

# ─── Automated Database Backup ───────────────────────────────
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))

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
