# AI News Daily Digest — Telegram Bot

## Goal

Build a Python program that runs via hermes-agent to extract and summarize the top 10 AI news stories from the past 24 hours, delivering a daily digest to Telegram users.

## Sources

Reputable news outlets:
- Wired
- The Economist
- Reuters
- TechCrunch
- The Verge
- Ars Technica
- MIT Technology Review
- Bloomberg Technology

## Output Format (Telegram Message)

1. **Brief Rundown** — A paragraph summarizing the overall AI landscape for the day: what's happening, key trends, major takeaways. Not too brief, not too detailed — the sweet spot for a busy reader who wants to stay informed.

2. **5 Must-Know Highlights** — Dot-format list of the most important stories, each with:
   - A concise but substantive summary (2-3 sentences)
   - Source attribution with clickable link for further reading

## Architecture

- **News Fetching**: Use NewsAPI or RSS feeds to pull AI-related articles from target sources within the last 24 hours
- **Summarization**: Use an LLM (Claude API) to generate the rundown and highlights from the collected articles
- **Delivery**: Send formatted message to Telegram users via Telegram Bot API
- **Orchestration**: hermes-agent runs the program on a schedule (daily)

## Tech Stack

- Python 3.11+
- hermes-agent (orchestration)
- NewsAPI / RSS parsing (feedparser)
- Claude API (summarization)
- python-telegram-bot (delivery)

## File Structure

```
projectclaude/
├── main.py              # Entry point — orchestrates fetch → summarize → deliver
├── fetcher.py           # News fetching from APIs/RSS
├── summarizer.py        # LLM-powered summarization
├── telegram_bot.py      # Telegram message formatting and delivery
├── config.py            # Configuration (API keys, source list, Telegram chat IDs)
├── requirements.txt     # Dependencies
└── .env                 # API keys (gitignored)
```

## Configuration

- `NEWS_API_KEY` — NewsAPI key for article fetching
- `ANTHROPIC_API_KEY` — Claude API key for summarization
- `TELEGRAM_BOT_TOKEN` — Telegram bot token
- `TELEGRAM_CHAT_ID` — Target chat/user ID for delivery
