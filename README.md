# AI News Daily Digest

A Python-powered Telegram bot that delivers a curated daily digest of the top AI news from reputable sources — summarized locally using [Ollama](https://ollama.com), zero API costs.

**What you get every morning:**

> **AI Daily Digest — March 25, 2026**
>
> AI regulation is heating up on multiple fronts — Bernie Sanders is pushing a bill to halt data center construction while a federal judge questioned the Pentagon's attempt to label Anthropic a supply-chain risk. Meanwhile, Arm is building its own AI chips and Kleiner Perkins just raised $3.5B to double down on AI investments.
>
> **Must-Know Highlights:**
> 1. **New Bernie Sanders AI Safety Bill Would Halt Data Center Construction** — A bipartisan coalition is proposing a moratorium on data center construction...
> 2. **Pentagon's 'Attempt to Cripple' Anthropic Is Troubling, Judge Says** — ...
>
> **Also Worth Knowing:**
> - [Kleiner Perkins raises $3.5B for AI](https://example.com) (TechCrunch)
> - [Granola hits $1.5B valuation](https://example.com) (TechCrunch)

## How It Works

```
RSS + page sources  →  Keyword Filter  →  Dedup  →  Configurable LLM  →  Telegram + archive
      ~2-10s            AI/ML terms            title      summarize        send + save copy
                        + entity names         similarity + rank
```

1. **Fetch** — Pulls articles from 7 RSS feeds plus Fortune's AI section page
2. **Fallback** — If a source returns 404, Cloudflare, or subscription-style blocking, retries with cloudscraper and then checks archived copies via the Wayback Machine / archive.ph
3. **Filter** — Keyword matching for AI relevance (general terms + entity names like OpenAI, DeepMind, NVIDIA, etc.)
4. **Dedup** — Removes duplicates by URL and title similarity (rapidfuzz, threshold ≥ 0.90)
5. **Summarize** — Sends top 20 articles to a configurable LLM provider/model (explicit env override or inherited agent primary provider/model)
6. **Deliver + Save** — Formats as Telegram HTML, sends to your chat/group, and archives a daily copy locally with 30-day retention

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- A Telegram bot (create one via [@BotFather](https://t.me/botfather))

### Setup

```bash
# Clone
git clone https://github.com/0xminion/test.git
cd test

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Pull an Ollama model
ollama pull minimax-m2.7:cloud    # recommended — fast, good quality
# or: ollama pull llama3.1:8b     # free, local-only, slower

# Configure
cp .env.example .env
chmod 600 .env
# Edit .env with your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

### Run

```bash
# Dry run — see the output without Telegram
python dry_run.py

# Full run — fetches, summarizes, sends to Telegram
python main.py
```

### Schedule with hermes-agent

```bash
hermes schedule add --name ai-digest --cmd "python main.py" --cron "0 7 * * *"
```

Or use cron directly:

```bash
crontab -e
# Add: 0 7 * * * cd /path/to/test && .venv/bin/python main.py
```

## Configuration

All config via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | — | Target chat/group ID |
| `LLM_PROVIDER` | No | `ollama` | LLM provider: `ollama`, `openai`, `openrouter`, or `anthropic` |
| `LLM_MODEL` | No | inherited or `minimax-m2.7:cloud` | Model name; inherits agent primary model if available |
| `LLM_API_BASE` | No | provider default | Optional custom API base |
| `OPENAI_API_KEY` | No | — | Required when `LLM_PROVIDER=openai` |
| `OPENROUTER_API_KEY` | No | — | Required when `LLM_PROVIDER=openrouter` |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `OLLAMA_MODEL` | No | `minimax-m2.7:cloud` | Legacy Ollama model fallback |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama API host |
| `RETENTION_DAYS` | No | `30` | Local daily report retention window |
| `DATA_DIR` | No | `./data` | Base directory for archived digest copies |
| `DELIVERY_HOUR` | No | `7` | Hour to deliver (24h format) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

## Getting Your Telegram Chat ID

1. Add your bot to a group (or start a DM with it)
2. Send any message in the chat
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id": <NUMBER>}` — that number is your `TELEGRAM_CHAT_ID`

## Project Structure

```
├── main.py              # Entry point — fetch → summarize → deliver
├── fetcher.py           # RSS fetching, keyword filtering, deduplication
├── summarizer.py        # Ollama API, prompt template, model swappability
├── telegram_bot.py      # HTML formatting, message splitting, Telegram API
├── storage.py           # Daily digest archive + retention pruning
├── config.py            # Configuration, env vars, source/keyword lists
├── dry_run.py           # Test run without Telegram
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── test_fetcher.py      # 18 unit tests
├── test_summarizer.py   # 7 unit tests
├── test_telegram_bot.py # 15 unit tests
└── test_config.py       # 2 unit tests
```

## Tests

```bash
pip install pytest
python -m pytest -v
# 42 tests, all passing
```

## Model Swappability

The summarizer is designed to be model-agnostic. All LLM calls go through `summarize(articles) -> str` in `summarizer.py`. To switch from Ollama to Claude, GPT, or any other provider, change only that function's implementation — everything else stays the same.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| RSS feed down | Skips that feed, continues with the rest |
| Ollama not running | Exits with code 1 and clear error message |
| Ollama timeout (120s) | Exits with code 1 |
| < 5 AI articles found | Delivers what's available with a "quiet day" note |
| Telegram send fails | Retries once, then exits with code 1 |
| Telegram 403 | Logs that bot was removed from chat, no retry |
| Message > 4096 chars | Automatically splits into multiple messages |

## Roadmap (v2)

- [ ] Trend tracking across days (what's heating up vs cooling down)
- [ ] Opinionated "hot take" section
- [ ] Multi-chat support (multiple Telegram groups)
- [ ] Cross-day deduplication
- [x] Full-text fallback scraping for Fortune AI section and blocked pages
- [ ] HN/Reddit as additional source signals

## License

MIT
