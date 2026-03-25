# AI News Daily Digest — Telegram Bot

## Goal

Build a Python program that runs via hermes-agent to extract and summarize the top AI news stories from the past 24 hours, delivering a daily digest to Telegram users.

## Sources

Reputable news outlets (via RSS):
- Wired
- TechCrunch
- The Verge
- Ars Technica
- MIT Technology Review
- Reuters
- VentureBeat (fallback)

## Output Format (Telegram Message)

1. **Brief Rundown** — A paragraph summarizing the overall AI landscape for the day
2. **5 Must-Know Highlights** — Numbered list with summaries and clickable source links

## Architecture

- **News Fetching**: RSS feeds via feedparser, keyword-filtered for AI relevance
- **Summarization**: Ollama (local LLM, default llama3.1:8b) — designed for model swappability
- **Delivery**: Telegram Bot API with HTML formatting
- **Orchestration**: hermes-agent runs `python main.py` on a daily schedule

## Tech Stack

- Python 3.11+
- hermes-agent (orchestration)
- feedparser (RSS parsing)
- Ollama (local LLM summarization)
- python-telegram-bot (delivery)
- rapidfuzz (deduplication)

## File Structure

```
projectclaude/
├── main.py              # Entry point — orchestrates fetch → summarize → deliver
├── fetcher.py           # RSS fetching + keyword filtering + deduplication
├── summarizer.py        # Ollama API calls, prompt template, model swappability
├── telegram_bot.py      # HTML message formatting + sending + splitting
├── config.py            # Configuration (env vars, source list, keywords)
├── requirements.txt     # Dependencies
├── .env.example         # Template for required env vars
├── .gitignore           # .env, __pycache__, etc.
├── test_fetcher.py      # Unit tests for fetcher
├── test_summarizer.py   # Unit tests for summarizer
├── test_telegram_bot.py # Unit tests for Telegram bot
└── test_config.py       # Unit tests for config
```

## Configuration

- `OLLAMA_MODEL` — Local model name (default: llama3.1:8b)
- `OLLAMA_HOST` — Ollama API host (default: http://localhost:11434)
- `TELEGRAM_BOT_TOKEN` — Telegram bot token from @BotFather
- `TELEGRAM_CHAT_ID` — Target chat/user ID for delivery
