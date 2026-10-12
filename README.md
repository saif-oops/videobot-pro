# 🎬 VideoBot Pro

A paid Telegram bot that plays and downloads videos from **Terabox** and **DiskWala** links.

## ✨ Features

- 📦 **Terabox** + 💾 **DiskWala** support
- ▶️ **Play** videos directly in Telegram (auto-plays in dashboard)
- ⬇️ **Download** with quality selection (1080p, 720p, 480p…)
- 📊 **Live progress bar** while downloading
- 🎫 **5 free videos** per user, then paid upgrade
- 💳 **₹99 Lifetime Premium** via Razorpay
- 🛡️ **Admin panel** — manage users, broadcast, view stats
- 🚀 **Railway deployment** ready

---

## 🚀 Quick Setup

### 1. Clone & Install

```bash
git clone <your-repo>
cd videobot
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables:
| Variable | Where to get |
|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | [@userinfobot](https://t.me/userinfobot) |
| `RAZORPAY_KEY_ID` | [Razorpay Dashboard](https://dashboard.razorpay.com) |
| `RAZORPAY_KEY_SECRET` | Razorpay Dashboard |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay → Settings → Webhooks |
| `WEBHOOK_URL` | Your Railway app URL |

### 3. Run Locally (Polling Mode)

```bash
python bot.py
```

---

## 🚂 Deploy to Railway

1. Push code to GitHub
2. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub**
3. Select your repo
4. Add environment variables (Settings → Variables)
5. Railway auto-deploys! Your URL: `https://your-app.up.railway.app`

### Set Razorpay Webhook

1. Go to [Razorpay Dashboard](https://dashboard.razorpay.com) → Settings → Webhooks
2. Add URL: `https://your-app.up.railway.app/webhook/razorpay`
3. Events to enable: `payment_link.paid`, `payment.captured`
4. Copy the **Webhook Secret** → paste in `RAZORPAY_WEBHOOK_SECRET`

---

## 👑 Admin Commands

| Command | Description |
|---|---|
| `/admin` or `/stats` | View bot statistics |
| `/grant @username` | Give premium to a user |
| `/revoke @username` | Remove premium |
| `/addquota @username 5` | Add 5 free uses |
| `/ban @username` | Ban a user |
| `/unban @username` | Unban a user |
| `/lookup @username` | View user info |
| `/broadcast message` | Send message to all users |

---

## 📁 Project Structure

```
videobot/
├── bot.py              # Main entry point
├── config.py           # Configuration
├── requirements.txt
├── Procfile            # Railway/Heroku start command
├── .env.example        # Environment template
├── handlers/
│   ├── start.py        # /start, /help, /status
│   ├── video.py        # Link detection, play, download
│   ├── admin.py        # Admin commands
│   └── payment.py      # Razorpay integration
├── utils/
│   ├── downloader.py   # yt-dlp + DiskWala scraper
│   ├── progress.py     # Live progress bar
│   ├── keyboards.py    # Inline keyboards
│   └── sessions.py     # Video session cache
└── database/
    ├── db.py           # DB init
    └── models.py       # Query functions
```

---

## ⚠️ Notes

- Telegram Bot API has a **50MB file size limit**. For larger videos, choose a lower quality.
- Terabox links are handled natively by yt-dlp.
- DiskWala uses a custom HTML scraper as fallback.
- Expired links won't work — always use fresh links.
