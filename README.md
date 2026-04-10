# AI News Daily Digest

A Python-powered Telegram bot that delivers a curated AI news digest with source clustering, signal-weighted ranking, cross-day deduplication, destination-specific output profiles, and room for future follow-builders integration.

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

1. **Fetch** — Pulls articles from RSS, page sources, and orthogonal signal feeds (arXiv, GitHub Blog AI/ML). Hacker News is enrichment-only and never appears as a standalone source.
2. **Fallback** — If a source returns 404, Cloudflare, or subscription-style blocking, retries with cloudscraper and then checks archived copies via the Wayback Machine / archive.ph
3. **Cluster + Dedup** — Groups same-day coverage into canonical story clusters and removes cross-day repeats against recent archives
4. **Rank** — Scores stories by recency, source trust, source breadth, HN technical attention, and topic momentum
5. **Trend Watch** — Uses persistent topic memory and archived daily payloads to identify what is heating up or cooling down
6. **Summarize** — Sends the ranked digest set to a configurable LLM provider/model with trend context and signal metadata
7. **Deliver + Save** — Renders destination-specific Telegram output profiles, saves daily artifacts, and preserves room for weekly highlights and follow-builders v2 integration

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
# Full run — fetches, clusters, ranks, summarizes, sends to Telegram
python main.py

# Weekly sample render from archived daily payloads
python - <<'PY'
from ai_news_digest.app import build_weekly_sample
payload, text = build_weekly_sample()
print(text)
PY
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
| `TELEGRAM_CHAT_ID` | No* | — | Single destination chat ID; can be comma-separated |
| `TELEGRAM_DESTINATIONS_JSON` | No* | — | JSON array for multi-chat delivery with optional per-destination bot tokens |
| `OLLAMA_MODEL` | No | `minimax-m2.7:cloud` | Legacy Ollama model fallback |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama API host |
| `RETENTION_DAYS` | No | `30` | Local daily report retention window |
| `CROSS_DAY_DEDUP_DAYS` | No | `7` | Dedup window against archived reports |
| `TREND_LOOKBACK_DAYS` | No | `7` | Lookback window for heating/cooling topic trends |
| `HN_ENABLED` | No | `true` | Enable Hacker News signal enrichment |
| `HN_MIN_POINTS` | No | `15` | Minimum HN points for a story signal |
| `HN_MIN_COMMENTS` | No | `5` | Minimum HN comments for a story signal |
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
ai_news_digest/
├── app.py                          # Daily + weekly orchestration
├── config/
│   ├── settings.py                # Env loading, runtime settings, destination profiles
│   └── catalog.py                 # Sources, keywords, trend topics, trust weights
├── sources/
│   ├── pipeline.py                # End-to-end fetch / cluster / rank pipeline
│   ├── rss.py                     # RSS ingestion
│   ├── pages.py                   # Page scraping + archive fallback
│   ├── hackernews.py              # HN enrichment-only signals
│   └── orthogonal.py              # arXiv / GitHub Blog signal layers
├── analysis/
│   ├── clustering.py              # Canonical story clustering
│   ├── ranking.py                 # Signal-weighted ranking
│   ├── trends.py                  # Heating / cooling topic tracking
│   └── weekly.py                  # Weekly highlights synthesis scaffolding
├── storage/
│   ├── archive.py                 # Daily/weekly artifacts, cross-day dedup, retention
│   └── topic_memory.py            # Persistent topic/entity memory + integration state
├── llm/
│   └── service.py                 # Provider routing + prompt assembly
├── output/
│   └── telegram.py                # Destination-specific Telegram rendering
└── integrations/
    └── follow_builders/
        └── adapter.py             # v2 integration seam for remote builder feeds

main.py                             # Thin daily entrypoint wrapper
config.py                           # Compatibility shim
fetcher.py                          # Compatibility shim
storage.py                          # Compatibility shim
summarizer.py                       # Compatibility shim
telegram_bot.py                     # Compatibility shim
examples/
├── sample-daily-digest.md
└── sample-weekly-highlights.md
```

## Tests

```bash
pip install pytest
python -m pytest -q
# 32 tests, all passing
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

- [x] Trend tracking across days (what's heating up vs cooling down)
- [x] Multi-chat support (multiple Telegram groups)
- [x] Cross-day deduplication
- [x] Full-text fallback scraping for Fortune AI section and blocked pages
- [x] Hacker News as an additional source signal (enrichment-only)
- [x] Signal-weighted ranking
- [x] Canonical story clustering
- [x] Persistent topic/entity memory
- [x] Destination-specific output profiles
- [x] Orthogonal signal layers (arXiv + GitHub Blog AI/ML)
- [ ] Weekly highlights full production CLI
- [ ] follow-builders deep integration

## License

MIT
