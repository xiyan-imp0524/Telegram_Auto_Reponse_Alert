# Workana to Telegram Bot

Monitors new **IT & Programming** assignments on [Workana](https://www.workana.com/jobs?category=it-programming) and sends optimized alerts to your Telegram bot.

## Why this is fast

Workana embeds job listings as JSON inside the HTML response. This project parses that payload directly with `httpx` — no browser automation, no Selenium, no Playwright.

That means:

- Lower CPU and memory usage
- Faster polling (default: every 2 minutes)
- Simple deployment on any VPS or local machine

## Features

- Scrapes Workana `it-programming` category
- Cleans and scores jobs based on your preferences
- Filters by skills, keywords, budget, bid count, and age
- Deduplicates with SQLite so you only get notified once
- Sends rich Telegram messages with title, budget, skills, and summary

## Setup

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy the token.

2. Get your chat ID:
   - Message your bot
   - Open `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Copy the `chat.id` value

3. Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

4. Configure environment:

```bash
copy .env.example .env
```

Edit `.env` with your token, chat ID, and filters.

## Instant mode with Workana session (recommended)

If you provide your `WORKANA_COOKIE`, the bot connects to Workana's **Pusher WebSocket** — the same push system their website uses when you're logged in. New IT & Programming jobs trigger Telegram alerts within about **1 second**.

```env
MONITOR_MODE=pusher
WORKANA_COOKIE=workana_session=your_session_here
```

Export the cookie from your browser while logged into Workana (DevTools → Application → Cookies).

## Polling fallback

If no cookie is set, the bot falls back to polling every 5 seconds:

```env
MONITOR_MODE=poll
```

## Configuration

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather |
| `TELEGRAM_CHAT_ID` | Destination chat ID |
| `POLL_INTERVAL_SECONDS` | Seconds between checks (default: **5**) |
| `MIN_POLL_INTERVAL_SECONDS` | Safety floor (default: 3, do not lower) |
| `BOOTSTRAP_ON_START` | Skip alerting for jobs already listed at startup |
| `WORKANA_LANGUAGE` | `en`, `es`, or `pt` |
| `WORKANA_CATEGORY` | Default: `it-programming` |
| `PREFERRED_SKILLS` | Comma-separated skills used for scoring |
| `KEYWORDS` | Only notify if title/description contains one |
| `EXCLUDED_KEYWORDS` | Skip jobs containing these terms |
| `MIN_BUDGET_USD` | Minimum budget ceiling in USD |
| `MAX_BIDS` | Skip crowded listings |
| `MAX_AGE_HOURS` | Ignore older postings |

## Scoring

Each job gets a relevance score based on:

- Matching preferred skills
- Keyword matches
- Low bid count (less competition)
- Higher budget
- Freshness (posted recently)
- Urgent flag

Jobs are sorted by score before notification.

## Project structure

```
telegram-bot/
├── main.py                 # Polling entry point
├── config.py               # Environment configuration
├── workana/
│   ├── scraper.py          # Workana HTML/JSON parser
│   ├── optimizer.py        # Filtering and scoring
│   └── storage.py          # SQLite deduplication
└── telegram_bot/
    └── notifier.py         # Telegram message sender
```

## Notes

- Workana has no public API; this uses the same embedded data their website renders.
- Respect Workana's terms of service and avoid aggressive polling.
- Keep your `.env` private — it contains your bot token.
