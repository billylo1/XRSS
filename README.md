# 🌟 XRSS - Your Twitter Feed, RSS-ified and Supercharged!

<div align="center">

[![License](https://img.shields.io/github/license/thytu/XRSS)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Docker Hub](https://img.shields.io/docker/pulls/thytu/xrss)](https://hub.docker.com/r/thytu/xrss)

<img src="https://i.ibb.co/87RF1jG/xrss.png" alt="XRSS Logo" width="200"/>

*Transform your Twitter experience into a delightful, distraction-free RSS feed!* 🚀

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](#-api-documentation) • [Contributing](#-contributing)

</div>

> **Note**: This project is a labor of love that transforms tweets into RSS feeds. While it might raise an eyebrow at Twitter HQ, we're all about making content more accessible! 🎭

## 🌈 What's XRSS?

XRSS is your passport to a cleaner, more organized Twitter experience. It transforms the chaotic Twitter timeline into a structured, filterable RSS feed that puts YOU in control. Perfect for researchers, developers, and anyone who loves their content well-organized!

### Why Choose XRSS?

- 🎯 **Laser-Focused**: Get exactly the content you want, nothing more
- 🚀 **Blazing Fast**: Redis-powered caching keeps everything snappy
- 🛠️ **Highly Customizable**: Filter by post types, users, and more
- 🐳 **Deploy Anywhere**: Docker-ready for instant deployment
- 🤝 **Developer Friendly**: Clean API with comprehensive documentation

## ✨ Features

Transform your Twitter experience with:

- 🎭 **Smart Feed Conversion**: Seamlessly transform Twitter/X feeds into clean RSS format
- 🎯 **Precision Filtering**: Cherry-pick exactly what you want to see (posts, replies, retweets, quotes)
- ⚡ **Lightning Fast**: Redis-powered caching system for instant responses
- 🛡️ **API Friendly**: Built-in rate limiting to keep you within bounds
- 🐳 **Deploy & Forget**: One-click deployment with Docker
- 🤖 **Always Fresh**: Background refresh keeps your content up-to-date

## 🚀 Getting Started

### Prerequisites

You'll need:
- 🐳 Docker & Docker Compose installed
- 🔑 Twitter/X account credentials
- ☕ A few minutes of your time

### Quick Setup

1. **Clone & Configure**
   ```bash
   # Get the example config
   curl -O https://raw.githubusercontent.com/thytu/xrss/main/.env.example
   mv .env.example .env
   # Edit .env with your Twitter credentials
   ```

2. **Choose Your Path**

   #### 🐳 Docker Way (Recommended)
   ```bash
   # Using Docker Compose (recommended)
   curl -O https://raw.githubusercontent.com/thytu/xrss/main/docker-compose.yml
   docker compose up -d

   # Or using Docker directly
   docker run -d \
     --name xrss \
     -p 8000:8000 \
     --env-file .env \
     vdematos/xrss:latest
   ```

   #### 🛠️ Manual Setup
   ```bash
   # From the repository root (after git clone)
   python3 -m venv venv
   source venv/bin/activate  # Windows: .\venv\Scripts\activate

   pip install -U pip
   pip install .             # application
   # pip install ".[dev]"   # optional: tests and linters

   # Requires Redis (see “Linux: full bare-metal setup” below). Then:
   uvicorn xrss.main:app --host 0.0.0.0 --port 8000
   ```

### Linux: full bare-metal setup

Use this on a fresh Linux server or workstation when you are **not** using Docker. You need **Python 3.10+**, **Redis**, and network access to **X/Twitter** (see cookies / proxy notes below).

#### 1. System packages

Debian / Ubuntu example:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git redis-server
sudo systemctl enable redis-server --now   # Redis on localhost:6379
redis-cli ping                             # expect PONG
```

Alternatively run only Redis in Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
export REDIS_URL=redis://127.0.0.1:6379
```

#### 2. Application install

```bash
git clone https://github.com/billylo1/XRSS.git
cd XRSS
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install .
```

Optional: generate **`cookies.json`** on this machine with Playwright (helps when X blocks password login):

```bash
pip install ".[cookies]"
playwright install chromium
playwright install-deps chromium   # Linux system libs for Chromium
```

On a **headless server** (no monitor / no `DISPLAY`), headed Chromium cannot start unless you use a virtual framebuffer:

```bash
sudo apt install -y xvfb
xvfb-run -a python scripts/generate_cookies_playwright.py --manual --browser chromium -o cookies.json
```

Or run **`--headless`** (often blocked by X login). The script exits early with a hint if headed mode is used without a display.

Use **`--from-export`** with a JSON export from a normal browser if Playwright is blocked or impractical.

#### 3. Configuration

```bash
cp .env.example .env
# Edit .env: TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD, REDIS_URL,
# optional TWITTER_TOTP_SECRET, TWITTER_PROXY, COOKIES_FILE, HOST, PORT
```

If X or Cloudflare blocks your server’s IP, set **`TWITTER_PROXY`** to an HTTP(S) or SOCKS proxy Twikit can use, or place a valid **`cookies.json`** from a logged-in browser session.

#### 4. Run the service

From the repo root with `venv` activated:

```bash
set -a && source .env && set +a   # optional: export vars from .env for this shell
uvicorn xrss.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
```

You can skip `source .env` if you only rely on **`python-dotenv`** inside the app: run Uvicorn from the repo root so `.env` is found when modules load.

Check:

- OpenAPI: `http://<host>:<port>/docs`
- RSS: `http://<host>:<port>/feed.xml`

#### 5. Firewall (optional)

If you expose the service:

```bash
sudo ufw allow 8000/tcp   # adjust port to match PORT in .env
sudo ufw reload
```

### 🎯 Access Your Feeds

Once running, your feeds are available at:
- 📰 RSS Feed: `http://localhost:8000/feed.xml`
- 📚 API Documentation: `http://localhost:8000/docs`

## 🔌 API Documentation

### Endpoints

#### 📡 GET `/feed.xml`
Your gateway to RSS-formatted Twitter feeds.

```http
GET /feed.xml?usernames=ylecun&usernames=karpathy&include_replies=false
```

| Parameter | Type | Default | Description |
|:----------|:-----|:---------|:------------|
| `usernames` | `List[str]` | `["ylecun"]` | Twitter handles to follow |
| `include_posts` | `bool` | `true` | Include regular tweets |
| `include_replies` | `bool` | `true` | Include reply tweets |
| `include_retweets` | `bool` | `true` | Include retweets |
| `include_quotes` | `bool` | `true` | Include quote tweets |

#### 🔍 POST `/`
Raw API endpoint for advanced users.

```json
{
  "usernames": ["user1", "user2"],
  "include_posts": true,
  "include_replies": true,
  "include_retweets": true,
  "include_quotes": true
}
```

## ⚙️ Configuration

### 🔐 Required Environment Variables

| Variable | Description |
|:---------|:------------|
| `TWITTER_USERNAME` | Your Twitter handle |
| `TWITTER_EMAIL` | Your Twitter email |
| `TWITTER_PASSWORD` | Your Twitter password |
| `TWITTER_TOTP_SECRET` | TOTP secret key (required if 2FA is enabled) |
| `REDIS_URL` | Redis connection string |

### 🔐 Two-Factor Authentication (TOTP) Setup

If your Twitter/X account has two-factor authentication enabled, you'll need to provide your TOTP secret key:

1. **Find Your TOTP Secret**: 
   - Go to Twitter Settings → Security and account access → Two-factor authentication
   - Select "Authentication app" and view your backup codes
   - Or extract the secret from your authenticator app's QR code

2. **Add to Environment**:
   ```bash
   export TWITTER_TOTP_SECRET=your_totp_secret_here
   ```

3. **Docker Users**:
   ```bash
   # Add to your .env file
   TWITTER_TOTP_SECRET=your_totp_secret_here
   ```

> **Note**: TOTP is optional - only needed if your account has 2FA enabled. The system will work normally without it for accounts that don't use two-factor authentication.

### 🎛️ Optional Tweaks

| Variable | Default | What it Does |
|:---------|:--------|:-------------|
| `CACHE_TTL` | `1800` | How long to cache (seconds) |
| `BACKGROUND_REFRESH_INTERVAL` | `1500` | How often to refresh (seconds) |
| `COOKIES_FILE` | `cookies.json` | Path to store authentication cookies |
| `TWITTER_PROXY` | _(unset)_ | HTTP(S) or SOCKS proxy URL for Twikit (when X blocks direct egress) |

### 🍪 Cookie Storage

XRSS stores authentication cookies to maintain your session. By default, they are stored in `cookies.json` in the current directory, but you can customize this:

```bash
# Store in your config directory
export COOKIES_FILE=~/.config/xrss/cookies.json

# Or in a local data directory
export COOKIES_FILE=./data/cookies/cookies.json
```

The directory structure will be created automatically if it doesn't exist.

## 🚄 Performance

We've optimized XRSS to be blazing fast:

- 🗄️ **Smart Caching**: Redis-powered with configurable TTL
- 🔄 **Proactive Updates**: Background refresh before cache expires
- 🚦 **Traffic Control**: Rate limiting (2 concurrent, 1s delay)
- ⚡ **Parallel Power**: Concurrent request processing
- 🔌 **Connection Smarts**: Efficient connection pooling
- 📦 **Data Efficiency**: Optimized serialization

## 🧪 Testing

```bash
# Get the dev goodies
pip install ".[dev]"

# Run the test suite
pytest

# Check the coverage
pytest  # Coverage included by default
```

## 🤝 Contributing

We love contributions! Here's how you can help:

1. 🍴 Fork it
2. 🌿 Create your branch: `git checkout -b feature/amazing-feature`
3. 🔄 Commit changes: `git commit -m 'Add amazing feature'`
4. ⤴️ Push to the branch: `git push origin feature/amazing-feature`
5. 🎯 Open a Pull Request

Check our [Contributing Guidelines](CONTRIBUTING.md) for more details!

## ⭐ Show Some Love

If this project helps you tame your Twitter feed, consider giving it a star! It helps others discover the project and makes our day! 🌟

---
<div align="center">

</div>
