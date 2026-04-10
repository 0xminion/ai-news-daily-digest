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
RSS + orthogonal signals + GitHub trending  →  Regex keyword filter  →  Cluster + Dedup  →  Rank  →  LLM (structured JSON)  →  Telegram + archive
      ~2-10s                                  word-boundary matching  title similarity    signal   validates + falls back      send + save copy
                                              (rejects false pos)     cross-day check     weights  to raw text on failure
```

1. **Fetch** — Pulls articles from RSS feeds, orthogonal signal feeds (arXiv, GitHub Blog AI/ML), and GitHub trending (top 3 fast-moving AI/ML repos daily). Hacker News is enrichment-only and never appears as a standalone source.
2. **Filter** — Regex-based keyword matching with word-boundary patterns. Handles `AI`, `A.I.`, rejects false positives like `maintain`, `Britain`. Tags matches for debugging.
3. **Cluster + Dedup** — Groups same-day coverage into canonical story clusters and removes cross-day repeats against recent archives.
4. **Rank** — Scores stories by recency, source trust, source breadth, HN technical attention, and topic momentum.
5. **Trend Watch** — Uses persistent topic memory and archived daily payloads to identify what is heating up or cooling down.
6. **Summarize** — Sends the ranked digest set to a configurable LLM provider/model. Returns structured JSON that's validated and converted to text. Falls back to raw text if JSON parsing fails.
7. **Deliver + Save** — Renders destination-specific Telegram output profiles, saves daily artifacts, and preserves room for weekly highlights and follow-builders v2 integration.

### Reliability

All external calls (RSS feeds, HN API, page scraping, archive.org, LLM providers) use **exponential backoff retry** (2-3 attempts, 5s initial delay, 2x backoff). A single transient failure no longer kills the whole digest.

## Output Format

Telegram output is rendered with normal title-case section headings, not all-caps blocks.

Links are embedded on the source name in Telegram HTML output, for example:

- Highlights: `Source: <clickable source name>`
- Also Worth Knowing: `Headline | <clickable source name>`
- Research / Builder Signals: `Headline | <clickable source name>`

The LLM returns structured JSON which is validated, then converted to the text format for Telegram delivery. If the LLM returns non-JSON text, the system falls back gracefully to raw text parsing.

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running (or another LLM provider)
- A Telegram bot (create one via [@BotFather](https://t.me/botfather))

### Setup

```bash
# Clone
git clone https://github.com/0xminion/ai-news-daily-digest.git
cd ai-news-daily-digest

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

# Fixture-backed format review (stable samples, no live fetch randomness)
python review_samples.py

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
# Add: 0 7 * * * cd /path/to/ai-news-daily-digest && .venv/bin/python main.py
```

## Configuration

All config via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Yes | — | Target chat/group ID (comma-separated for multiple) |
| `TELEGRAM_DESTINATIONS_JSON` | No* | — | JSON array for multi-chat delivery with per-destination bot tokens |
| `LLM_PROVIDER` | No | `ollama` | LLM provider: `ollama`, `openai`, `openrouter`, or `anthropic` |
| `LLM_MODEL` | No | `minimax-m2.7:cloud` | Model name |
| `LLM_API_BASE` | No | provider default | Optional custom API base |
| `OPENAI_API_KEY` | No | — | Required when `LLM_PROVIDER=openai` |
| `OPENROUTER_API_KEY` | No | — | Required when `LLM_PROVIDER=openrouter` |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama API host |
| `RETENTION_DAYS` | No | `30` | Local daily/weekly report retention window |
| `CROSS_DAY_DEDUP_DAYS` | No | `7` | Dedup window against archived reports |
| `TREND_LOOKBACK_DAYS` | No | `7` | Lookback window for heating/cooling topic trends |
| `RESEARCH_SIGNALS_COUNT` | No | `5` | Max items in Research / Builder Signals |
| `HN_ENABLED` | No | `true` | Enable Hacker News signal enrichment |
| `HN_MIN_POINTS` | No | `15` | Minimum HN points for a story signal |
| `HN_MIN_COMMENTS` | No | `5` | Minimum HN comments for a story signal |
| `GITHUB_TRENDING_ENABLED` | No | `true` | Enable GitHub trending repo source |
| `GITHUB_TRENDING_TOP_N` | No | `3` | Number of trending AI/ML repos to include |
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
│   ├── __init__.py                # Public API re-exports
│   ├── settings.py                # Env loading, runtime settings, destination profiles
│   ├── catalog.py                 # Re-export hub (backward compat)
│   ├── feeds.py                   # RSS feeds, page sources, orthogonal feeds, GitHub trending config
│   ├── keywords.py                # Regex-based AI keyword matching (word-boundary patterns)
│   ├── topics.py                  # Trend topics, HN signal queries
│   └── trust.py                   # Source trust weights
├── prompts/
│   ├── daily.md                   # Daily digest prompt (structured JSON output)
│   └── weekly.md                  # Weekly highlights prompt
├── sources/
│   ├── pipeline.py                # End-to-end fetch / cluster / rank pipeline
│   ├── rss.py                     # RSS ingestion (with retry)
│   ├── pages.py                   # Page scraping + archive fallback + SSRF protection
│   ├── hackernews.py              # HN enrichment-only signals (with retry)
│   ├── orthogonal.py              # arXiv / GitHub Blog signal layers
│   └── github_trending.py         # GitHub trending AI/ML repos (scrapes github.com/trending)
├── analysis/
│   ├── clustering.py              # Canonical story clustering
│   ├── ranking.py                 # Signal-weighted ranking
│   ├── trends.py                  # Heating / cooling topic tracking
│   └── weekly.py                  # Weekly highlights synthesis scaffolding
├── storage/
│   ├── archive.py                 # Daily/weekly artifacts, cross-day dedup, retention
│   └── topic_memory.py            # Persistent topic/entity memory + integration state
├── llm/
│   └── service.py                 # Provider routing + structured JSON output + validation
├── output/
│   └── telegram.py                # Destination-specific Telegram rendering
├── utils/
│   └── retry.py                   # Exponential backoff retry decorator
└── integrations/
    └── follow_builders/
        └── adapter.py             # v2 integration seam for remote builder feeds

main.py                             # Daily entrypoint
weekly.py                           # Weekly entrypoint
review_samples.py                   # Sample output generator
examples/
├── fixtures/                       # Test payloads
├── sample-daily-digest.md
└── sample-weekly-highlights.md
docs/                               # Design docs
```

## Tests

```bash
pip install pytest
python -m pytest -q
# 36 tests, all passing
```

## LLM Provider Swappability

The summarizer is model-agnostic. All LLM calls go through `summarize(...) -> str` in `ai_news_digest/llm/service.py`. Supports:

- **Ollama** — local, free, default
- **OpenAI** — GPT-4, GPT-4o, etc.
- **OpenRouter** — access to 100+ models via single API
- **Anthropic** — Claude models

Change `LLM_PROVIDER` and `LLM_MODEL` in `.env`. The structured JSON output format is requested from all providers (with `response_format: json_object` for OpenAI, system prompt instruction for others). Falls back to raw text if JSON parsing fails.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| RSS feed down | Retries 2x with backoff, then skips that feed |
| HN API timeout | Retries 2x with backoff, then skips HN for that query |
| Page fetch blocked (Cloudflare) | Falls back to cloudscraper, then archive.org, then archive.ph |
| Ollama/LLM not running | Exits with code 1 and clear error message |
| LLM returns malformed JSON | Falls back to raw text parsing (backward compatible) |
| LLM API error | Retries 3x with exponential backoff (5s → 10s → 20s) |
| < 5 AI articles found | Delivers what's available with a "quiet day" note |
| Telegram send fails | Retries once, then exits with code 1 |
| Telegram 403 | Logs that bot was removed from chat, no retry |
| Message > 4096 chars | Automatically splits into multiple messages |
| SSRF attempt in URL | Blocks localhost, private IPs, cloud metadata endpoints |

## Security

- **SSRF protection** — page scraper blocks `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, private IPs (`10.x`, `172.16-31.x`, `192.168.x`), cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`, etc.)
- **Prompt injection** — article content is sanitized before passing to the LLM (regex strips common injection patterns)
- **No credential exposure** — API keys are read from environment, never logged or passed to external services except their intended provider

## Roadmap (v2)

- [x] Trend tracking across days (what's heating up vs cooling down)
- [x] Multi-chat support (multiple Telegram groups)
- [x] Cross-day deduplication
- [x] Hacker News as an additional source signal (enrichment-only)
- [x] Signal-weighted ranking
- [x] Canonical story clustering
- [x] Persistent topic/entity memory
- [x] Destination-specific output profiles
- [x] Orthogonal signal layers (arXiv + GitHub Blog AI/ML)
- [x] GitHub trending repos (top 3 AI/ML daily)
- [x] Regex-based keyword matching (replaces brittle substring filter)
- [x] Externalized LLM prompts (prompts/ directory)
- [x] Structured JSON output with validation + fallback
- [x] Exponential backoff retry on all external calls
- [x] Config split into modular files (feeds, keywords, topics, trust)
- [x] SSRF hardening (private IP blocking)
- [ ] Weekly highlights full production CLI
- [ ] follow-builders deep integration
- [ ] Content enrichment for top articles (full-text fetch before LLM)

## License

MIT
