# Sportsbook Dashboard

Local web dashboard for managing a sportsbook agent operation. Scrapes account data from allagentreports.com, ingests payment emails from Gmail, and lets you link payments to accounts.

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/ethanstogsdill-hash/sb.git
cd sb
python setup.py

# 2. Configure credentials
cp .env.example .env
# Edit .env with your site credentials

# 3. Activate venv and run
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

python -m uvicorn app.main:app --reload
```

Open **http://localhost:8000**

## Features

- **Agent Scraping** — Playwright-based scraper bypasses Cloudflare to pull account data from allagentreports.com
- **Gmail Integration** — OAuth2 connection to scan for payment emails (Venmo, Zelle, Cash App, PayPal)
- **Payment Linking** — Link payments to agent accounts via dropdown
- **Auto-Refresh** — Background scraping (15min) and Gmail scanning (10min)
- **Real Name Editing** — Inline editable real names persist across scrapes

## Gmail OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**
3. Create OAuth 2.0 credentials (Web application type)
4. Set redirect URI to `http://localhost:8000/api/gmail/callback`
5. Add Client ID and Client Secret to `.env`

## Tech Stack

- **Backend:** FastAPI, aiosqlite, Playwright
- **Frontend:** Vanilla JS, Tailwind CSS (CDN)
- **Database:** SQLite (WAL mode)
