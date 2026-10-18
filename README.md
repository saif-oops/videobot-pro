# 🎬 VideoBot Pro

<p align="center">
  <img src="bot_icon.jpg" alt="VideoBot Pro Banner" width="220" style="border-radius: 16px;">
</p>

<p align="center">
  <strong>High-performance Telegram Bot & Web Mini App for TeraBox and DiskWala video streaming and downloading.</strong>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-deployment">Deployment</a> •
  <a href="#-admin-commands">Admin Guide</a> •
  <a href="#-architecture">Architecture</a>
</p>

---

## ✨ Features

- ⚡ **Multi-Platform Support**: Fast, reliable extraction for **TeraBox** (and all 35+ mirror domains like `1024tera`, `terasharelink`, `teraboxlinke`) and **DiskWala** links.
- 📱 **Telegram Web Mini App**: Built-in responsive SPA player supporting direct HLS streaming and client-side WASM signing (`AppiCrypt`).
- 📥 **Flexible Downloads**: Download videos directly through Telegram or the browser with quality selection and live progress bars.
- ⏱️ **Auto-Delete Messages**: Configurable privacy timer (e.g. 30 minutes) to automatically scrub sent videos and media cards from chat.
- 🎫 **Freemium Quota System**: Free uses limit (default 5 videos) with automated VIP upgrade prompts.
- 💳 **Integrated Payments**:
  - Automated **Razorpay** webhook processing with instant VIP role granting.
  - Native **UPI** deep-linking and dynamic QR code generation.
- 📢 **Force-Subscribe (FSUB)**: Require users to join your Telegram channel before accessing video streams.
- 🛡️ **Hardened Anti-SSRF Security**: Strict domain whitelisting, private loopback/RFC-1918 blocking, and redirect inspection on all streaming endpoints.
- 👑 **Comprehensive Admin Suite**: User lookups, quota adjustment, VIP grants/revocations, channel broadcasts, and automated database backups.

---

## 📁 Project Structure

```
videobot/
├── bot.py                  # Main entry point (Starlette ASGI + Telegram Bot)
├── config.py               # Central environment configuration & domain lists
├── requirements.txt        # Python package dependencies
├── Procfile                # Heroku / Railway deployment declaration
├── Dockerfile              # Production multi-stage Docker container
├── docker-compose.yml      # Container composition with persistent volumes
├── .env.example            # Environment configuration template
├── database/
│   ├── db.py               # SQLite schema initialization and migrations
│   └── models.py           # Async ORM queries, user sessions, and settings
├── handlers/
│   ├── start.py            # /start, /help, /status, and referral system
│   ├── video.py            # Link parsing, extraction cards, and downloads
│   ├── admin.py            # Admin panel, user management, and broadcast
│   └── payment.py          # Razorpay payment verification and UPI intents
├── utils/
│   ├── downloader.py       # yt-dlp wrapper, extraction routines, and URL normalizer
│   ├── keyboards.py        # Telegram inline button keyboards
│   ├── fsub.py             # Force-subscribe verification logic
│   ├── progress.py         # Real-time progress bar calculation
│   └── sessions.py         # Web player session authorization
├── web/
│   └── static/
│       ├── index.html      # Web Mini App SPA
│       ├── player.js       # Player controls, ad countdown & HLS engine
│       ├── style.css       # Mobile-first glassmorphism styling
│       ├── qt.txt          # Client-side signing payload
│       └── pkg/            # AppiCrypt WASM cryptographic module
└── tests/
    ├── test_domains.py     # Domain detection and URL normalization tests
    └── test_security.py    # SSRF defense and route permission tests
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- FFmpeg (required for video processing)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### 2. Clone & Install

```bash
git clone https://github.com/your-username/videobot.git
cd videobot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure `.env`

Copy the sample environment file and configure your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_IDS=123456789
```

### 4. Run the Bot

```bash
python bot.py
```

The bot runs in long-polling mode locally while serving the Web Mini App on `http://localhost:8080`.

---

## ⚙️ Configuration Reference

| Variable | Description | Required | Default |
|---|---|:---:|:---:|
| `BOT_TOKEN` | Telegram Bot Token from [@BotFather](https://t.me/BotFather) | **Yes** | — |
| `ADMIN_IDS` | Comma-separated list of admin numeric Telegram User IDs | **Yes** | — |
| `WEBHOOK_URL` | Public HTTPS domain for webhook and streaming proxy | Recommended | `""` (polling mode) |
| `PORT` | Web server listening port | No | `8080` |
| `DB_PATH` | Path to SQLite database file | No | `videobot.db` |
| `AUTO_DELETE_MINUTES` | Minutes before delivered video messages are deleted | No | `30` |
| `RAZORPAY_KEY_ID` | Razorpay API Key ID | Optional | `""` |
| `RAZORPAY_KEY_SECRET` | Razorpay API Key Secret | Optional | `""` |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Webhook signing secret | Optional | `""` |
| `RAZORPAY_PAYMENT_URL` | Hosted Razorpay payment link | Optional | `""` |
| `UPI_ID` | UPI ID for direct QR and intent payments | Optional | `""` |
| `UPI_NAME` | Payee display name for UPI payments | Optional | `VideoBot Admin` |
| `FSUB_CHANNEL` | Channel username (e.g. `@MyChannel`) for force-subscribe | Optional | `""` |
| `BACKUP_INTERVAL_HOURS` | Interval for automated database backups sent to admins | No | `24` |

---

## 🚂 Deployment

### Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

1. Fork or push this repository to your GitHub account.
2. In Railway, click **New Project** → **Deploy from GitHub repo**.
3. Under **Variables**, add `BOT_TOKEN`, `ADMIN_IDS`, and `WEBHOOK_URL` (set to your Railway domain `https://<your-app>.up.railway.app`).
4. Attach a **Persistent Volume** mounted at `/app/data` and configure `DB_PATH=/app/data/videobot.db` to preserve database records across deployments.

### Deploy with Docker

```bash
# Build the container
docker build -t videobot-pro .

# Run container with persistent storage
docker run -d \
  --name videobot \
  --restart unless-stopped \
  -p 8080:8080 \
  --env-file .env \
  -v videobot_data:/app/data \
  videobot-pro
```

Or using Docker Compose:

```bash
docker compose up -d
```

---

## 👑 Admin Commands

All admin commands require your Telegram ID to be listed in `ADMIN_IDS`.

| Command | Usage | Description |
|---|---|---|
| `/admin` or `/stats` | `/stats` | View real-time system stats, active users, and earnings |
| `/grant` | `/grant @user [days]` | Upgrade user to VIP (defaults to 30 days) |
| `/revoke` | `/revoke @user` | Remove VIP access from a user |
| `/addquota` | `/addquota @user [count]` | Add bonus free uses to a user's balance |
| `/lookup` | `/lookup @user` | Inspect detailed user history, uses, and tier |
| `/ban` / `/unban` | `/ban @user` | Restrict or restore a user's access |
| `/broadcast` | `/broadcast Message` | Broadcast announcement to all registered users |
| `/setchannel` | `/setchannel @channel` | Change the force-subscribe channel dynamically |
| `/autodelete` | `/autodelete 30` | Update message auto-delete timer (`1`, `30`, `off`) |
| `/setad` | `/setad TAG_ID` | Configure Monetag ad zone tag for Web Mini App |
| `/backup` | `/backup` | Request an instant SQLite database backup |

---

## 🧪 Testing

Run the automated test suite to verify domain normalization and SSRF defenses:

```bash
python tests/test_domains.py
python tests/test_security.py
```

---

## 🔒 Security

This bot includes comprehensive defense-in-depth protection:
- **SSRF Hardening**: All streaming proxy endpoints validate destinations against an approved list of CDN domains, block IPv4/IPv6 private address spaces (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16), and enforce HTTPS scheme checks.
- **Header Forwarding**: Protects against open-redirect hopping by validating response redirect locations before following.

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).
