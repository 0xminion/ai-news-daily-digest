---
name: ai-news-digest
category: dev
description: >
  End-to-end AI news digest pipeline — RSS ingestion, LLM summarization,
  structured JSON output, and Telegram MarkdownV2 formatting.
  Universal formatting spec for model-agnostic compliance.
requires:
  - python 3.11+
  - ollama (optional, for local inference)
  - telegram bot token (optional, for delivery)
---

# AI News Digest — Formatting & Structure Rules

> **Skill trigger:** load this skill before any `ai-news-daily-digest` run
> to enforce output formatting compliance across all models.

---

## 1. Section Layout (fixed order)

```
Brief Rundown:
<2–3 sentence overview>

Highlights:
1. [Headline](url)
<summary body>
Source: Publication Name

Also Worth Knowing:
- [Headline](url) (Publication Name)

Research / Builder Signals:
- [paper] [Headline](url) (Publication Name)
- [repo] [Headline](url) (Publication Name)
```

| Section | Items | Detail level |
|---------|-------|-------------|
| Brief Rundown | 1 | 2–3 sentences |
| Highlights | 3–5 | headline + summary + source |
| Also Worth Knowing | up to 10 | headline + source (NO body) |
| Research / Builder Signals | up to 5 | subtype + headline + source |

---

## 2. Headline Markdown Embed — The Golden Rule

ALL headlines are links. Period.

| Section | Pattern |
|---------|---------|
| Highlights | `1. [Headline text](https://example.com)` |
| Also Worth Knowing | `- [Headline text](https://example.com) (Source)` |
| Research / Builder Signals | `- [subtype] [Headline text](https://example.com) (Source)` |

### CRITICAL: Also Worth Knowing — full headline, never truncate

- Render the **complete headline** inside `[...]`
- Never truncate with `…`, never abbreviate
- The title IS the link text; the link text IS the title
- If the headline is long, the link text is long — Telegram's 4096-char chunker handles overflow

```
# ✅ Correct
- [Canonical lays out a plan for AI in Ubuntu Linux](https://...) (The Verge)

# ❌ Wrong — truncation destroys the link
- [Canonical lays out a plan for AI…](https://...) (The Verge)
```

### Numbered List Format — The `N.` Rule

In the **Highlights** section, always use plain numbered lists:
- Correct: `1.`, `2.`, `3.`
- **Wrong:** `1\.`, `2\.`, `3\.`

Do NOT escape the period after the number. The formatter will normalize `N\.` to `N.` if encountered, but the LLM must be instructed to never emit it.

### Highlights rendering

```
1. [Microsoft and OpenAI gut their exclusive deal, freeing OpenAI to sell on AWS and Google Cloud](https://...)
The companies announced a sweeping overhaul...
Source: VentureBeat
```

---

## 3. Research / Builder Signals — Subtype Prefix Rules

Subtypes are metadata labels that appear as `[paper]`, `[repo]`, `[builder feed]`, or `[product / launch]`.

**In LLM prompts:** ask for `"subtype": "paper"` (no brackets)
**In text output:** renderer wraps it → `[paper] [title](url)`

```
# What the LLM produces in JSON
{ "subtype": "paper", "headline": "Math Takes Two", ... }

# What the renderer produces
- [paper] [Math Takes Two](https://arxiv.org/...) (arXiv AI)
```

**Escaped brackets are normalized** before renderer sees them:
```python
first = first.replace('\\[', '[').replace('\\]', ']')
```

---

## 4. Telegram MarkdownV2 Rendering

Telegram's MarkdownV2 requires escaping these chars outside code blocks:
```
_  *  [  ]  (  )  ~  `  >  #  +  -  =  |  {  }  .  !
```

All text runs through `_mdv2_escape()` before Telegram send.

### Highlight formatting
```
**[Title](url)**   ← bold + link
<body>
Source: Publication Name
```

### Also Worth Knowing formatting
```
• [Title](url) (Publication Name)
```

### Research / Builder Signals formatting
```
• [paper] [Title](url) (Publication Name)
```

**Banned in output:** `<b>`, `</a>`, HTML tags, raw URLs instead of embeds, merged bullet lines.

---

## 5. HTML Sanitization — Two Gates

| Stage | Tool | Purpose |
|-------|------|---------|
| Before LLM | `BeautifulSoup.get_text()` + `html.unescape()` | strip HTML from RSS |
| After LLM (formatter) | `_strip_html()` | strip residual LLM hallucinated HTML |

**Critical fix in `_strip_html`:** preserve line boundaries

```python
# ✅ Correct — sections stay matchable
return '\n'.join(' '.join(line.split()) for line in text.splitlines())

# ❌ Wrong — collapses sections into one line
return ' '.join(text.split())
```

---

## 6. Section Heading Normalization

The formatter normalizes case-variant headings before parsing:

| Input (any case) | Normalized to |
|---|---|
| `BRIEF RUNDOWN:` | `Brief Rundown:` |
| `highlights:` | `Highlights:` |
| `Also Worth Knowing:` | `Also Worth Knowing:` |
| `Research / Builder Signals:` | `Research / Builder Signals:` |

Regexes match case-insensitively; the formatter then splits by canonical forms.

---

## 7. Bullet Line Merging Fix

Some LLMs cram multiple items on one line:
```
- [Item one](url) (Source) - [Item two](url) (Source)
```

Pre-processor splits at `) - ` before `[`:
```python
MERGE_SPLIT_RE = re.compile(r'\)\s+-\s+(?=\[)')
```

---

## 8. Model-Specific Compliance Checklist

All models must produce output compatible with these rules. Use the prompt below as the universal spec.

### Universal LLM Prompt Rules

```
You are an AI news curator. ... produce a daily digest.

Rules:
- Never use HTML tags; use plain text only (URLs in Markdown [text](url) format).
- Hacker News is enrichment-only. Do not list it as a standalone source.
- Research / Builder Signals must be its own separate section.
- Keep Research / Builder Signals to at most 5 items.
- If a signal has a subtype, preserve it like [paper], [repo], etc.
- Numbered lists must use `N.` (e.g., `1.`, `2.`). **Never escape the period:** do NOT output `N\.` in Highlights.

You MUST respond with valid JSON matching this exact schema:
{
  "brief_rundown": "...",
  "highlights": [{"headline": "...", "summary": "...", "source": "...", "url": "...", "why_it_matters": "..."}],
  "also_worth_knowing": [{"headline": "...", "source": "...", "url": "..."}],
  "research_builder_signals": [{"headline": "...", "source": "...", "url": "...", "subtype": "..."}]
}
```

### Model-Specific Notes

| Model | Caveat |
|---|---|
| **kimi-k2.6:cloud** | Generation is slow (~20 chars/sec). Set `OLLAMA_TIMEOUT=600`. Often puts reasoning in `reasoning` field instead of `content` — formatter already handles fallback. |
| **kimi-k2.7:cloud** | Same structure compliance as k2.6. Increase timeout further if context is large. |
| **minimax-m2.7:cloud** | Fast (~140 chars/sec). Standard timeout 120s is fine. **Known formatting quirk:** Occasionally escapes numbered list periods (`4\.`). Ensure prompt explicitly instructs `N.` without backslash, or rely on post-process normalization. |
| **gemma4:31b-cloud** | May produce fewer structured signals; validate JSON strictly. |

### Model Auto-Detection

The pipeline auto-detects the running model from `~/.hermes/config.yaml` via `_resolve_hermes_llm_defaults()`. No hardcoding needed — it follows the agent's current model.

---

## 9. Verification Pipeline

Before claiming formatting is correct:

1. Run `_format_digest(test_input)` and inspect raw output strings
2. Check `any('[paper]' in msg for msg in messages)` for research signals
3. Check `any('[Headline](url)' in msg for msg in messages)` for embeds
4. Check `any('Source:' in msg for msg in messages)` for attribution
5. Check escaped brackets: `\\[` must be cleaned before assertion
6. Run full test suite: `python -m pytest tests/test_telegram_bot.py -xvs`
7. Run live digest: `python3 main.py` and visually inspect output

---

## 10. Quick Reference

| Concern | Rule |
|---|---|
| Headline links | `[Title](url)` everywhere |
| Numbered list items | `1.`, `2.` — never `1\.`, `2\.` |
| Also Worth Knowing truncation | **NEVER** — full headline |
| Subtype prefix | `[paper]`, `[repo]`, `[builder feed]`, `[product / launch]` |
| Telegram escaping | `_mdv2_escape()` on all text |
| HTML | Banned — stripped at two gates |
| Merged bullets | Split by `) - ` pattern |
| Section headings | Normalized to title case before parsing |
| Line boundaries | Preserved in `_strip_html` |

---

## 11. New Architecture (v2)

### YAML-First Configuration
All settings live in `config/default.yaml` (mandatory). Environment variables override via `AI_DIGEST__section__key=value`.
- `config/feeds/*.yaml` — feed fragment files, deep-merged at load time
- `config/dev.yaml` / `config/prod.yaml` — environment overrides

### Semantic Clustering
Articles are clustered by cosine similarity of title+snippet embeddings from `qwen3-embedding:0.6b` (or configured `embedding.model`). If the embedding endpoint is unavailable, falls back to singleton clusters (no data loss).

### Circuit Breaker
Per-source health is tracked in SQLite (`source_health` table). Sources with consecutive failures or zero-article timeouts are automatically excluded from fetching. Configurable via `circuit_breaker` section in YAML.

### Entity Extraction
LLM extracts people, organizations, coins, and projects from the daily digest. Results are persisted to SQLite and surfaced in weekly reports.

### Observability Metrics
Lightweight metrics logged at INFO level: `pipeline_start`, `pipeline_success`/`failure` (with latency), `fetch_latency` (per source), `articles_fetched`, `fetch_failed`, `dedup_hit_rate`.

---

## 12. Operational Notes

### Agent-Native Summarization Mode (Default)

As of the latest version, the default LLM provider is `"agent"` — the running agent generates the summary directly. No external API keys, no Ollama setup, no local models required.

**How it works (file handshake):**
```
1. python3 main.py
   → Fetches articles, builds prompt, saves to data/agent_prompt.json
   → Prints "AGENT SUMMARIZATION REQUIRED" and exits with code 2

2. Agent reads data/agent_prompt.json, generates structured JSON digest,
   saves response to data/agent_response.json

3. python3 main.py
   → Reads agent_response.json, validates JSON, formats for Telegram
   → Auto-deletes response file to prevent stale data on next run
```

**For fully automated cron jobs**, pass the pre-generated summary via env var:
```bash
AGENT_DIGEST_JSON='{"brief_rundown":"...","highlights":[...]}' python3 main.py
```

**Switching to external LLM** (Ollama/OpenRouter/Anthropic/OpenAI):
```bash
# Override via env var
AI_DIGEST__llm__provider=ollama AI_DIGEST__llm__model=minimax-m2.7:cloud python3 main.py

# Or edit config/default.yaml
llm:
  provider: ollama
  model: minimax-m2.7:cloud
```

---

### Config Cascade Gotcha — Env Vars Override YAML Silently

The pipeline loads config in this order: `default.yaml` → `dev.yaml`/`prod.yaml` → `.env` (via dotenv) → legacy env vars (`OLLAMA_MODEL`, `LLM_PROVIDER`, etc.).

**Critical finding:** If your `.env` file sets `OLLAMA_MODEL=minimax-m2.7:cloud`, it will silently override `config/default.yaml` even after you change the YAML. To fully switch the default provider to `"agent"`, you must:
1. Update `config/default.yaml` → `llm.provider: agent`
2. Update `config/dev.yaml` → `llm.provider: agent` (dev overrides default)
3. Update `config/prod.yaml` → `llm.provider: agent` (prod overrides default)
4. Remove `OLLAMA_MODEL` and `LLM_PROVIDER` from your `.env` file

**Verification:**
```python
from ai_news_digest.config import get_llm_settings
print(get_llm_settings()['provider'])  # Should print "agent"
```

---

### YAML Env Override Format

Environment variables override nested YAML keys using the `AI_DIGEST_` prefix with **single underscore** delimiters and **double underscore** for nesting:

```bash
# Correct — single underscore after AI_DIGEST, double underscore for nesting
AI_DIGEST_embedding__semantic_clustering_enabled=false
AI_DIGEST_llm__provider=ollama
AI_DIGEST_llm__model=minimax-m2.7:cloud

# Wrong — double underscore after AI_DIGEST breaks parsing
AI_DIGEST__embedding__semantic_clustering_enabled=false   # ❌ Does NOT work
```

---

### RSS Source Debugging & Fallback Chain

When an RSS source appears to "fail" (zero articles, timeout, or circuit breaker trip), diagnose in this order:

1. **Direct curl test:** `curl -sL -w "HTTP %{http_code}\n" <feed_url> | head -20`
2. **Feedparser validation:** Parse locally and check `len(feed.entries)`
3. **Google News RSS proxy:** For major publishers with dead direct feeds, use:
   ```
   https://news.google.com/rss/search?q=site:reuters.com+technology&hl=en-US&gl=US&ceid=US:en
   ```
   This bypasses bot protection and CDN blocks that kill direct publisher RSS.
4. **Update `config/feeds/core.yaml`** with the working URL, then clear health state:
   ```python
   from ai_news_digest.storage.sqlite_store import _conn
   with _conn() as c:
       c.execute("DELETE FROM source_health WHERE source_name = 'Dead Source'")
       c.commit()
   ```

**Real-world case (April 2026):**
- `rss-bridge.org` proxy for Reuters died with HTTP 000 (unreachable host)
- Direct `reuters.com/technology/` returned HTTP 401 to bots
- `feeds.reuters.com` DNS did not resolve
- **Working fix:** Google News RSS search proxy (see above)

---

### Circuit Breaker Death Spiral — Critical Anti-Pattern

**Symptom:** Over multiple days, ALL RSS sources become permanently disabled even though their feeds are healthy. The SQLite `source_health` table shows `consecutive_failures = 3` and `last_success = None` for every source.

**Root cause:** Two interacting bugs in `analysis/health.py`:
1. `source_check(source_name, success=True, article_count=0)` was treated as a **failure**, incrementing `consecutive_failures`. A source that publishes 1 article/day and misses the AI keyword filter would rack up 3 "failures" and be permanently disabled.
2. `filter_disabled_sources()` had a **zero-article timeout**: any source with `last_article_count == 0` was blocked for 48h. Once blocked, the next run fetched 0 articles, updating `last_article_count` to 0 again — a **permanent death spiral** that eventually blocked all sources.

**Fix:**
```python
# In source_check() — ONLY increment failures on actual exceptions
if success:
    rec["consecutive_failures"] = 0  # Zero-article fetch is NOT a failure
    rec["last_success"] = datetime.now(timezone.utc).isoformat()
    rec["last_article_count"] = article_count
else:
    rec["consecutive_failures"] += 1

# In filter_disabled_sources() — REMOVE the zero-article timeout entirely
# RSS feeds are lightweight; a 48h ban after one quiet day is unnecessary
# and creates the death spiral.
```

**Verification after fix:**
```python
from ai_news_digest.analysis.health import filter_disabled_sources
from ai_news_digest.config import RSS_FEEDS
active = filter_disabled_sources(RSS_FEEDS)
print([name for name, _ in active])  # Should list ALL feeds, not empty
```

---

### Embedding Endpoint Configuration

**Default:** `qwen3-embedding:0.6b` via Ollama on `http://localhost:11434`

**Batching is mandatory for performance.** The legacy `/api/embeddings` endpoint handles one text per request. For 200+ research articles, this is ~25 minutes. The batched `/api/embed` endpoint cuts this to ~5 minutes.

**Config (`config/default.yaml`):**
```yaml
embedding:
  model: qwen3-embedding:0.6b
  host: "http://localhost:11434"
  similarity_threshold: 0.85
  semantic_clustering_enabled: false
  batch_size: 16
```

**Implementation:**
```python
# Use /api/embed (batched), NOT /api/embeddings (single-request)
def _fetch_embeddings_batch(texts: list[str]) -> list[np.ndarray | None]:
    resp = requests.post(
        f"{host}/api/embed",
        json={"model": model, "input": texts},
        timeout=120,
    )
    data = resp.json()
    return [np.array(e, dtype=np.float32) for e in data["embeddings"]]
```

**Benchmarks (qwen3-embedding:0.6b, local CPU):**
| Method | 200 articles | Per article |
|---|---|---|
| `/api/embeddings` (single) | ~25 min | ~7.5s |
| `/api/embed` (batch 16) | ~5 min | ~0.5s |

**Verification:**
```bash
ollama list  # Must show qwen3-embedding:0.6b
curl -s http://localhost:11434/api/embed -d '{"model": "qwen3-embedding:0.6b", "input": ["test"]}' | jq '.embeddings | length'
# → 1
```

---

### RSS Ingestion — HTML Source Contamination
- **Root cause:** VentureBeat, Ars Technica, TechCrunch emit raw HTML in RSS summaries: `<a href="...">`, `<b>`, `&#x27;` entities, merged bullet lines
- **Fix at parser level:** `sources/rss.py` → `BeautifulSoup.get_text()` + `html.unescape()` before LLM ingest
- **Never allow HTML to reach:** LLM context OR Telegram output

### LLM Timeout — kimi-k2.6:cloud
- **Default timeout (120s) fails:** `ReadTimeout` after 3 retries with 3.5min generation time.
- **Required:** Set `llm.timeout: 600` in YAML when using kimi-k2.6 via Ollama.
- **Performance tradeoff:** kimi-k2.6 ~20 chars/sec vs minimax-m2.7 ~140 chars/sec. Use kimi when structured JSON quality matters; use minimax when latency matters.

### Debugging Format Failures
- When `TestFormatDigest` assertions fail, run `_format_digest(test_input)` directly and inspect raw output.
- If sections are missing, trace upstream: `_strip_html` → `_normalize_heading_variants` → `_parse_summary_sections` before suspecting the formatter.
