# AI News Daily Digest

A Python-powered Telegram bot that delivers a curated AI news digest with source clustering, semantic deduplication, signal-weighted ranking, cross-day dedup, destination-specific output profiles, Hermes agent auto-detection, entity extraction, and a YAML-first configuration system.

**What you get every morning:**

> **AI Daily Digest — April 29, 2026**
>
> OpenAI and Musk are in court, Poolside released a new coding model, and enterprise GPU FOMO is driving prices up.
>
> **Highlights**
> 1. **[Sam Altman is "the face of evil"...](https://arstechnica.com/...)** — The lawsuit alleges OpenAI knew about violent ChatGPT users...
> 2. **[Poolside launches Laguna XS.2...](https://venturebeat.com/...)** — Free open model for local agentic coding.
>
> **Also Worth Knowing**
> • [I've Covered Robots for Years. This One Is Different](https://www.wired.com/...) (Wired)
>
> **Research / Builder Signals**
> • [paper] [Judging the Judges...](https://arxiv.org/...) (arXiv AI)
> • [repo] [CJackHwang/ds2api](https://github.com/...) (GitHub Trending)

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
- An AI agent (Hermes, Claude Code, OpenCode, etc.) — the agent itself generates the summary, no external LLM API needed
- A Telegram bot (create one via [@BotFather](https://t.me/botfather)) — *only if* you want Telegram delivery

### Setup

```bash
# Clone
git clone https://github.com/0xminion/ai-news-daily-digest.git
cd ai-news-daily-digest

# Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
chmod 600 .env
# Edit .env with your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID if using Telegram
```

### Run

**Agent-native mode (default) — no API keys, no Ollama:**

```bash
# Step 1: Fetch articles and build the prompt
python main.py
# → The script prints "AGENT SUMMARIZATION REQUIRED" and saves the prompt to data/agent_prompt.json

# Step 2: Your agent reads the prompt and generates the structured JSON digest,
#    then saves it to data/agent_response.json

# Step 3: Re-run to format and deliver
python main.py
```

When running inside a Hermes session, the agent detects the prompt automatically,
generates the summary, writes the response file, and re-runs the pipeline.

**With an external LLM (optional):**

```bash
# Ollama (local)
ollama pull minimax-m2.7:cloud
LLM_PROVIDER=ollama LLM_MODEL=minimax-m2.7:cloud python main.py

# OpenRouter
LLM_PROVIDER=openrouter LLM_MODEL=moonshotai/kimi-k2.6 OPENROUTER_API_KEY=*** python main.py
```

**Telegram delivery:**

```bash
python main.py --telegram
python weekly.py --telegram
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

All configuration is **YAML-first** with zero hardcoded Python defaults.

### Layer order
1. `config/default.yaml` — mandatory base config
2. `config/{ENV}.yaml` — environment override (`dev`, `prod`, etc.)
3. `config/feeds/*.yaml` — feed fragment files (deep-merged)
4. Environment variables — override anything (`AI_DIGEST__llm__model=kimi-k2.6:cloud`)

### Key files

| File | Purpose |
|------|---------|
| `config/default.yaml` | Base settings: LLM, delivery, fetching, ranking, circuit breaker, embedding |
| `config/dev.yaml` | Dev overrides (stdout output, INFO logging) |
| `config/prod.yaml` | Prod overrides (telegram output, WARNING logging) |
| `config/feeds/core.yaml` | Core RSS feeds |
| `config/feeds/orthogonal.yaml` | arXiv / GitHub Blog signal feeds |

### Environment overrides

Legacy env vars are still supported and mapped into the YAML tree:

```bash
OLLAMA_MODEL=minimax-m2.7:cloud      # → llm.model
TELEGRAM_BOT_TOKEN=xxx               # → delivery.bot_token
OUTPUT_MODE=telegram                 # → delivery.output_mode
AI_DIGEST__embedding__model=my-model # → embedding.model (new prefix style)
```

### Old `.env` config (still supported for secrets)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | When `OUTPUT_MODE=telegram` | — | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | When `OUTPUT_MODE=telegram` | — | Target chat/group ID |
| `OPENAI_API_KEY` | No | — | Required when `LLM_PROVIDER=openai` |
| `OPENROUTER_API_KEY` | No | — | Required when `LLM_PROVIDER=openrouter` |
| `ANTHROPIC_API_KEY` | No | — | Required when `LLM_PROVIDER=anthropic` |

All non-secret settings have moved to YAML. See `config/default.yaml` for the full schema.

## Getting Your Telegram Chat ID

1. Add your bot to a group (or start a DM with it)
2. Send any message in the chat
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id": <NUMBER>}` — that number is your `TELEGRAM_CHAT_ID`

## Project Structure

```
config/
├── default.yaml               # Mandatory base config (source of truth)
├── dev.yaml                    # Dev environment overrides
├── prod.yaml                   # Prod environment overrides
└── feeds/
    ├── core.yaml               # Core RSS feeds
    └── orthogonal.yaml         # arXiv / GitHub Blog signal feeds

ai_news_digest/
├── app.py                      # Daily + weekly orchestration
├── config/
│   ├── __init__.py            # Public API re-exports
│   ├── yaml_loader.py         # Mandatory YAML config loader with hot-reload
│   ├── settings.py            # Backward-compatible settings shim
│   ├── validate.py            # Config validation
│   ├── feeds.py               # YAML-driven feed loader
│   ├── keywords.py            # Regex-based AI keyword matching
│   ├── topics.py              # Trend topics, HN signal queries
│   └── trust.py               # Source trust weights
├── prompts/
│   ├── daily.md               # Daily digest prompt (structured JSON output)
│   └── weekly.md              # Weekly highlights prompt
├── sources/
│   ├── pipeline.py            # End-to-end fetch / cluster / rank pipeline
│   ├── rss.py                 # RSS ingestion (with retry + circuit breaker)
│   ├── pages.py               # Page scraping + archive fallback + SSRF protection
│   ├── hackernews.py          # HN enrichment-only signals
│   ├── orthogonal.py          # arXiv / GitHub Blog signal layers
│   └── github_trending.py     # GitHub trending AI/ML repos
├── analysis/
│   ├── clustering.py          # Canonical story clustering (exact + fuzzy)
│   ├── semantic_clustering.py # Embedding-based clustering (qwen3-embedding:0.6b)
│   ├── ranking.py             # Signal-weighted ranking
│   ├── trends.py              # Heating / cooling topic tracking
│   ├── relevance.py           # User-preference relevance filtering
│   ├── health.py              # Circuit breaker (source health in SQLite)
│   ├── entities.py            # LLM-based named entity extraction
│   └── weekly.py              # Weekly highlights synthesis
├── storage/
│   ├── archive.py             # Daily/weekly artifacts, cross-day dedup, retention
│   ├── sqlite_store.py        # SQLite backend (runs, topic memory, entities, FTS)
│   └── topic_memory.py        # Backward-compat shim over sqlite_store
├── llm/
│   └── service.py             # Provider routing + token guard + structured JSON
├── output/
│   └── telegram.py            # Destination-specific Telegram MarkdownV2 rendering
├── observability/
│   └── metrics.py             # Lightweight pipeline metrics (latency, counts, dedup)
├── utils/
│   └── retry.py               # Exponential backoff retry decorator
└── integrations/
    └── follow_builders/
        └── adapter.py         # v2 integration seam for remote builder feeds

main.py                             # Daily entrypoint
weekly.py                           # Weekly entrypoint
dry_run.py                          # Quick dry run (fetch + sample render, no LLM)
full_dry_run.py                     # Full pipeline dry run (fetch + summarize + print)
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

- **Agent (default)** — the running agent generates the summary; no API keys, no local models
- **Ollama** — local, free
- **OpenAI** — GPT-4, GPT-4o, etc.
- **OpenRouter** — access to 100+ models via single API
- **Anthropic** — Claude models
- **Hermes auto-detect** — follows your active agent model automatically (when using external LLM mode)

Change `LLM_PROVIDER` and `LLM_MODEL` in `.env`, or set `AI_DIGEST__llm__provider=ollama`.
The structured JSON output format is requested from providers that support it. Falls back to raw text if JSON parsing fails. Reasoning models (e.g. kimi-k2.6) are handled by reading the `reasoning` field when `content` is empty.

**Agent mode automation:** For fully hands-off cron jobs, pre-generate the summary JSON and pass it via the `AGENT_DIGEST_JSON` environment variable:

```bash
AGENT_DIGEST_JSON='{"brief_rundown":"...","highlights":[...]}' python main.py
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Agent summarization required (default) | Saves prompt to `data/agent_prompt.json`, prints instructions, exits with code 2 |
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

- [x] YAML-first configuration (zero hardcoded Python defaults)
- [x] Semantic clustering with Ollama embeddings (qwen3-embedding:0.6b)
- [x] SQLite state backend (runs, topic memory, entities, daily/weekly reports, FTS5 search)
- [x] Circuit breaker for source health (auto-disable failing feeds)
- [x] LLM-based entity extraction (people, orgs, coins, projects)
- [x] Observability metrics (pipeline latency, fetch counts, dedup hit rate)
- [x] User-preference relevance filtering (interests/avoid profiles)
- [x] Trend tracking across days
- [x] Multi-chat support (multiple Telegram groups)
- [x] Cross-day deduplication
- [x] Hacker News as an additional source signal (enrichment-only)
- [x] Signal-weighted ranking
- [x] Canonical story clustering
- [x] Destination-specific output profiles
- [x] Orthogonal signal layers (arXiv + GitHub Blog AI/ML)
- [x] GitHub trending repos (top 3 AI/ML daily)
- [x] Regex-based keyword matching
- [x] Externalized LLM prompts
- [x] Structured JSON output with validation + fallback
- [x] Exponential backoff retry on all external calls
- [x] SSRF hardening
- [x] Token guard (context window truncation)
- [x] Hermes agent auto-detection
- [x] Reasoning-model compatibility (kimi-k2.6)
- [ ] Weekly highlights full production CLI
- [ ] follow-builders deep integration
- [ ] Content enrichment for top articles (full-text fetch before LLM)
- [ ] Archive web UI (search + browse)

## License

MIT
