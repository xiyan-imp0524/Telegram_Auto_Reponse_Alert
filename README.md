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

