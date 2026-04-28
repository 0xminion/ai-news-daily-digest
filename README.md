# AI News Daily Digest

A Python-powered Telegram bot that delivers a curated AI news digest with source clustering, signal-weighted ranking, cross-day deduplication, destination-specific output profiles, and Hermes agent auto-detection.

**What you get every morning:**

> **AI Daily Digest — April 23, 2026**
>
> Enterprise AI agents took center stage as OpenAI and Google unveiled new workspace tools designed to automate business tasks, while Google challenged Nvidia's compute dominance with new TPUs. Meanwhile, robotics gained momentum with Tesla's earnings and Sony's ping-pong bot, even as concerns over the environmental impact of gas-powered data centers grew.
>
> **Heating Up:**
> • Google / DeepMind — 9 articles today vs 1.83 avg previously
> • AI Agents — 9 articles today vs 2.5 avg previously
>
> **Highlights**
> 1. **[OpenAI unveils Workspace Agents...](https://venturebeat.com/...)** — OpenAI introduced agents that perform tasks across Slack, Google Drive, and Salesforce.
> 2. **[Google doesn't pay the Nvidia tax...](https://venturebeat.com/...)** — Eighth-gen TPUs for training and agentic inference.
>
> **Also Worth Knowing**
> • [Google updates Workspace to make AI your new office intern](https://techcrunch.com/...) (TechCrunch)
>
> **Research / Builder Signals**
> • [repo] [langfuse/langfuse: Open source LLM engineering platform](https://github.com/langfuse/langfuse) (GitHub Trending)

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

Telegram output uses normal title-case section headings with clickable headline links:

- **Highlights**: Headline is a clickable link; summary and source follow.
- **Also Worth Knowing**: `[Headline](url) (Source)`
- **Research / Builder Signals**: `[paper]` / `[repo]` / `[builder feed]` / `[product / launch]` prefix before the headline link.

The LLM returns structured JSON which is validated, then converted to the text format for Telegram delivery. If the LLM returns non-JSON text, the system falls back gracefully to raw text parsing.

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running (or another LLM provider)
- An LLM with **at least 200k context length** (`kimi-k2.6:cloud`, Claude Sonnet, or another 200k+ model)
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

# Pull an Ollama model (default fallback)
ollama pull minimax-m2.7:cloud    # recommended — fast, good quality
# or: ollama pull gemma4:31b-cloud

# Configure
cp .env.example .env
chmod 600 .env
# Edit .env with your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

### Run

```bash
# Default — fetches, clusters, ranks, summarizes, prints to stdout (no Telegram setup needed)
python main.py

# Deliver to Telegram (requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
python main.py --telegram

# Same for weekly
python weekly.py          # stdout
python weekly.py --telegram
```

### Hermes Agent Auto-Detection (Recommended)

If you run this inside a Hermes agent session, the digest **automatically uses the same model and provider** as your active agent — no manual `.env` configuration needed for the LLM. It reads `~/.hermes/config.yaml` and resolves credentials at runtime.

Supported Hermes providers:
- **Nous Research** → maps to OpenAI-compatible API
- **OpenRouter** → uses pooled credentials
- **Anthropic** → uses pooled credentials
- **Ollama / custom** → falls back to local Ollama

To override auto-detection, set explicit env vars:

```bash
LLM_PROVIDER=anthropic LLM_MODEL=claude-3-5-sonnet-20240620 python main.py
```

### Schedule with cron

```bash
crontab -e
# Add: 0 7 * * * cd /path/to/ai-news-daily-digest && .venv/bin/python main.py
```

## Hermes Skill (Recommended)

This repo ships a Hermes skill at `SKILL.md` that enforces formatting compliance
across **all** models — kimi, minimax, gemma, claude, or gpt.

### Install the skill

```bash
# From the repo root
ln -sf "$(pwd)/SKILL.md" ~/.hermes/skills/ai-news-digest/SKILL.md
```

The skill automatically loads whenever you run the digest inside a Hermes session.

### What the skill enforces

- **Section layout** — fixed order: Brief Rundown → Highlights → Also Worth Knowing → Research / Builder Signals
- **Headline links** — `[Title](url)` everywhere; titles are **never truncated**
- **Subtype prefixes** — `[paper]`, `[repo]`, `[builder feed]`, `[product / launch]`
- **MarkdownV2 escaping** — `_mdv2_escape()` on all Telegram text
- **HTML sanitization** — two-gate pipeline: RSS parser + post-LLM formatter
- **Section heading normalization** — case-insensitive matching before parsing
- **Bullet merge fix** — splits `) - [` patterns into separate items
- **Model-specific notes** — timeout tuning per model (kimi needs 600s, minimax 120s)

### Loading the skill in cron jobs

When scheduling via `cronjob`, attach the skill so formatting rules are always present:

```bash
# One-shot run
hermes cronjob create \
  --schedule "0 7 * * *" \
  --name "ai-news-digest" \
  --skills ai-news-digest \
  --prompt "Run the AI news daily digest for today and deliver to Telegram."
```

Or in your `crontab` directly, the skill is automatically discovered when the
agent runs from the repo directory (Hermes resolves `.` in `cwd` and loads
matching skills from `~/.hermes/skills/`).

## Configuration

All config via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OUTPUT_MODE` | No | `stdout` | `stdout` prints digest to console; `telegram` delivers via Telegram bot |
| `TELEGRAM_BOT_TOKEN` | When `OUTPUT_MODE=telegram` | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | When `OUTPUT_MODE=telegram` | — | Target chat/group ID (comma-separated for multiple) |
| `TELEGRAM_DESTINATIONS_JSON` | No* | — | JSON array for multi-chat delivery with per-destination bot tokens |
| `LLM_PROVIDER` | No | auto-detect | `ollama`, `openai`, `openrouter`, `anthropic` |
| `LLM_MODEL` | No | auto-detect | Model name for a **200k+ context** model (e.g. `claude-3-5-sonnet-20240620`, `kimi-k2.6:cloud`) |
| `LLM_API_BASE` | No | provider default | Optional custom API base |
| `LLM_CONTEXT_LIMIT` | No | auto-infer | Optional explicit context length for custom or less-common 200k+ models |
| `LLM_TIMEOUT` | No | `120` | LLM request timeout in seconds |
| `LLM_MAX_TOKENS` | No | `1800` | Max tokens for LLM response |
| `OPENAI_API_KEY` | No | — | Required when `LLM_PROVIDER=openai` |
| `OPENROUTER_API_KEY` | No | — | Required when `LLM_PROVIDER=openrouter` |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama API host |
| `OLLAMA_MODEL` | No | `minimax-m2.7:cloud` | Default Ollama model |
| `RETENTION_DAYS` | No | `30` | Local daily/weekly report retention window |
| `CROSS_DAY_DEDUP_DAYS` | No | `7` | Dedup window against archived reports |
| `TREND_LOOKBACK_DAYS` | No | `7` | Lookback window for heating/cooling topic trends |
| `RESEARCH_SIGNALS_COUNT` | No | `5` | Max items in Research / Builder Signals |
| `HN_ENABLED` | No | `true` | Enable Hacker News signal enrichment |
| `HN_MIN_POINTS` | No | `15` | Minimum HN points for a story signal |
| `HN_MIN_COMMENTS` | No | `5` | Minimum HN comments for a story signal |
| `ORTHOGONAL_SIGNALS_ENABLED` | No | `true` | Enable arXiv / GitHub Blog signal feeds |
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
│   ├── settings.py                # Env loading, runtime settings, destination profiles, Hermes auto-detect
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
│   └── weekly.py                  # Weekly highlights synthesis (LLM + deterministic fallback)
├── storage/
│   ├── archive.py                 # Daily/weekly artifacts, cross-day dedup, retention
│   └── topic_memory.py            # Persistent topic/entity memory
├── llm/
│   └── service.py                 # Provider routing + structured JSON output + validation + reasoning-model support
├── output/
│   └── telegram.py                # Destination-specific Telegram rendering
├── utils/
│   └── retry.py                   # Exponential backoff retry decorator
└── integrations/
    └── follow_builders/
        └── adapter.py             # v2 integration seam for remote builder feeds

main.py                             # Daily entrypoint
weekly.py                           # Weekly entrypoint
dry_run.py                          # Quick dry run (fetch + sample render, no LLM)
full_dry_run.py                     # Full pipeline dry run (fetch + summarize + print, no Telegram)
review_samples.py                   # Sample output generator from fixtures
examples/
├── fixtures/                       # Test payloads
├── sample-daily-digest.md
└── sample-weekly-highlights.md
docs/                               # Design docs
```

## Tests

```bash
pip install -r requirements.txt pytest
python -m pytest -q
# currently 70+ tests
```

## LLM Provider Swappability

The summarizer is model-agnostic. All LLM calls go through `summarize(...) -> str` in `ai_news_digest/llm/service.py`. Supports:

- **Ollama** — local, free, default fallback
- **OpenAI** — GPT-4, GPT-4o, etc.
- **OpenRouter** — access to 100+ models via single API
- **Anthropic** — Claude models
- **Hermes auto-detect** — follows your active agent model automatically

Change `LLM_PROVIDER` and `LLM_MODEL` in `.env`, or let Hermes auto-detect handle it. The structured JSON output format is requested from providers that support it. Falls back to raw text if JSON parsing fails. Reasoning models (e.g. kimi-k2.6) are handled by reading the `reasoning` field when `content` is empty.

**Project requirement:** the digest rejects models inferred below 200k context length. For custom 200k+ models that are not in the built-in model map, set `LLM_CONTEXT_LIMIT` explicitly.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| RSS feed down | Retries 2x with backoff, then skips that feed |
| HN API timeout | Retries 2x with backoff, then skips HN for that query |
| Page fetch blocked (Cloudflare) | Falls back to cloudscraper, then archive.org, then archive.ph |
| Ollama/LLM not running | Exits with code 1 and clear error message |
| LLM returns malformed JSON | Falls back to raw text parsing (backward compatible) |
| LLM API error | Retries 3x with exponential backoff (5s → 10s → 20s) |
| LLM prompt too large | Token guard progressively truncates articles to fit context window |
| Reasoning model returns empty content | Falls back to `reasoning` field automatically |
| < 5 AI articles found | Delivers what's available with a "quiet day" note |
| Telegram send fails | Retries once, then exits with code 1 |
| Telegram 403 | Logs that bot was removed from chat, no retry |
| Message > 4096 chars | Automatically splits into multiple messages |
| SSRF attempt in URL | Blocks localhost, private IPs, cloud metadata endpoints |

## Security

- **SSRF protection** — page scraper blocks `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, private IPs (`10.x`, `172.16-31.x`, `192.168.x`), cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`, etc.)
- **Prompt injection** — article content is sanitized before passing to the LLM (regex strips common injection patterns)
- **No credential exposure** — API keys are read from environment, never logged or passed to external services except their intended provider

## Roadmap

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
- [x] Token guard (context window truncation)
- [x] Hermes agent auto-detection
- [x] Reasoning-model compatibility (kimi-k2.6)
- [ ] Weekly highlights full production CLI
- [ ] follow-builders deep integration
- [ ] Content enrichment for top articles (full-text fetch before LLM)

## License

MIT
