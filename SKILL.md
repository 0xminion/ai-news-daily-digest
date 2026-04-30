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
<summary body — Source Name>

Also Worth Knowing:
- [Headline](url) (Publication Name)

Research and Builder Signals:
- [paper] [Headline](url) (Publication Name)
- [repo] [Headline](url) (Publication Name)
```

| Section | Items | Detail level |
|---------|-------|-------------|
| Brief Rundown | 1 | 2–3 sentences |
| Highlights | 3–5 | headline + summary + source |
| Also Worth Knowing | up to 10 | headline + source (NO body) |
| Research and Builder Signals | up to 5 | subtype + headline + source |

---

## 2. Headline Markdown Embed — The Golden Rule

ALL headlines are links. Period.

| Section | Pattern |
|---------|---------|
| Highlights | `1. [Headline text](https://example.com)` |
| Also Worth Knowing | `- [Headline text](https://example.com) (Source)` |
| Research and Builder Signals | `- [subtype] [Headline text](https://example.com) (Source)` |

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
The companies announced a sweeping overhaul... — VentureBeat
```

### Universal formatting constraints (all models must obey)

| Constraint | Rule |
|---|---|
| **No emoji in headlines** | NEVER prefix highlights with emoji (e.g. `🏗️`, `💰`). Emojis belong in thread intros or section headers only if the platform supports them. |
| **No `/` in section titles** | Use `Research and Builder Signals` not `Research / Builder Signals`. The slash character breaks some parsers and looks unprofessional in plain-text outputs. |
| **Source inline with em-dash** | In highlights, append the source to the summary with an em-dash: `Summary text — Source Name`. Do NOT use a separate `Source:` line. |

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

**Section header spacing — critical for Telegram:**
In `_format_digest`, join section parts with `\n\n`, NOT `\n`. A single newline causes Telegram to glue the previous section's last line to the next header:

```python
# ❌ Wrong — header sticks to previous content
parts.append(f'**Also Worth Knowing**\n{also}')

# ✅ Correct — blank line before header
parts.append(f'**Also Worth Knowing**\n\n{also}')
```

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
- Research and Builder Signals must be its own separate section.
- Keep Research and Builder Signals to at most 5 items.
- If a signal has a subtype, preserve it like [paper], [repo], etc.
- Numbered lists must use `N.` (e.g., `1.`, `2.`). **Never escape the period:** do NOT output `N\.` in Highlights.
- NEVER put emoji in headlines or section titles.
- NEVER use the `/` character in section titles. Use "and" instead.
- In highlights, put the source inline at the end of the summary with an em-dash: "Summary text — Source Name". Do NOT use a separate "Source:" line.

You MUST respond with valid JSON matching this exact schema:
{
  "brief_rundown": "...",
  "highlights": [{"headline": "...", "summary": "...", "source": "...", "url": "...", "why_it_matters": "..."}],
  "also_worth_knowing": [{"headline": "...", "source": "...", "url": "..."}],
  "research_builder_signals": [{"headline": "...", "source": "...", "url": "...", "subtype": "..."}],
  "entities": [{"name": "...", "type": "..."}]
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
7. Run full test suite: `python -m pytest tests/test_telegram_bot.py -xvs`
8. Run live digest: `python3 scripts/daily.py` and visually inspect output

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
| **Section header spacing** | **`\n\n`** between `Highlights` / `Also Worth Knowing` / `Research` in `_format_digest` |
| **No emoji in headlines** | Headlines are plain text — emoji only in thread intros if needed |
| **No `/` in titles** | Use `and` instead of `/` in all section and article titles |
| **Source inline** | `Summary text — Source Name` (not separate `Source:` line) |

---

## 11. Twitter and X Thread Format

Twitter does not render Markdown links in tweets — URLs are auto-linked. The thread format is optimized for readability in plain text.

### Thread Structure

```
🧵 AI Daily Digest — April 30, 2026

The AI landscape today is dominated by...

1/ SoftBank is creating a robotics company that builds data centers
SoftBank is reportedly forming a new entity called Roze... — TechCrunch
https://techcrunch.com/...

2/ Anthropic could raise a new $50B round at a valuation of $900B
Anthropic is reportedly in talks to raise $50 billion... — TechCrunch
https://techcrunch.com/...
```

### Twitter Formatting Rules

| Rule | Implementation |
|---|---|
| **No bold** | Twitter has no bold text. Do NOT use `**text**` or HTML `<b>`. |
| **No markdown links in body** | URLs are pasted as raw links on their own line. Twitter auto-links them. |
| **No emoji on individual tweet titles** | Keep headlines clean. Emojis only in the thread intro tweet if desired. |
| **Source inline with em-dash** | `Summary text — Source Name` |
| **Numbered as `N/` or `N.`** | Thread tweets use `1/`, `2/` etc. Numbered list items use `1.`, `2.` |
| **Max 280 chars per tweet** | The renderer chunks automatically; individual items should stay under limit. |

---

## 12. Agent-Native Entity Extraction

When `llm.provider` is set to `"agent"`, the agent that generates the digest also extracts entities. No external LLM API call is needed for entity extraction.

### How It Works

1. The agent prompt schema includes an `entities` array:
```json
{
  "entities": [
    {"name": "OpenAI", "type": "org"},
    {"name": "Sam Altman", "type": "person"}
  ]
}
```

2. The agent populates this array while writing the digest.

3. `summarize_with_entities()` returns a `DigestResult` containing both `.text` and `.entities`.

4. `app.py` passes `pre_extracted=result.entities` to `extract_and_record_entities()`, which skips the LLM call and records directly to SQLite.

### Valid Entity Types

| Type | Examples |
|---|---|
| `person` | Sam Altman, Demis Hassabis |
| `org` | OpenAI, Anthropic, Google |
| `coin` | Bitcoin, Ethereum, Solana |
| `project` | GPT-5, Claude, Gemini |
| `topic` | RAG, agentic AI, multimodal |

### Fallback

If the agent does not provide entities (empty array or missing key), the pipeline falls back to LLM-based extraction for non-agent providers. Agent mode never makes an extra LLM call for entities.

---

## 13. New Architecture (v2)

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

**Agent-native mode:** When `llm.provider: agent`, the agent that writes the digest also populates the `entities` array in the structured JSON. No external LLM call is made for entity extraction — the pipeline reads pre-extracted entities directly from the agent response. See section 12 for details.

### Observability Metrics
Lightweight metrics logged at INFO level: `pipeline_start`, `pipeline_success`/`failure` (with latency), `fetch_latency` (per source), `articles_fetched`, `fetch_failed`, `dedup_hit_rate`.

---

## 12. Operational Notes

### Agent-Native Summarization Mode (Default)

As of the latest version, the default LLM provider is `"agent"` — the running agent generates the summary directly. No external API keys, no Ollama setup, no local models required.

**How it works (file handshake):**
```
1. python3 scripts/daily.py
   → Fetches articles, builds prompt, saves to data/agent_prompt.json
   → Prints "AGENT SUMMARIZATION REQUIRED" and exits with code 2

2. Agent reads data/agent_prompt.json, generates structured JSON digest,
   saves response to data/agent_response.json

3. python3 scripts/daily.py
   → Reads agent_response.json, validates JSON, formats for Telegram
   → Auto-deletes response file to prevent stale data on next run
```

**For fully automated cron jobs**, pass the pre-generated summary via env var:
```bash
AI_DIGEST_embedding__semantic_clustering_enabled=true AI_DIGEST_SKIP_RESEARCH_EMBEDDING=true python3 scripts/daily.py
```

**Switching to external LLM** (Ollama/OpenRouter/Anthropic/OpenAI):
```bash
# Override via env var
AI_DIGEST__llm__provider=ollama AI_DIGEST__llm__model=minimax-m2.7:cloud python3 scripts/daily.py

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

### Embedding Benchmarks & Defaults — Live Findings (April 2026)

After running the full pipeline with semantic clustering enabled, disabled, and core-only, the data is unambiguous:

| Variant | Articles Embedded | Wall Time | Output Diff vs Off |
|---------|-------------------|-----------|-------------------|
| Full (core + research) | 208 (32 + 176) | ~660s | Zero (research timed out, fell back to singletons) |
| Core-only | 32 | ~97s | Zero |
| **Off (default)** | **0** | **~9s** | **Zero** |

**Key finding:** At typical daily volume (30–40 diverse core articles), no pair of articles had cosine similarity ≥ 0.85. Every article stayed as its own singleton cluster. The embedding step added ~90s of pure CPU burn with **zero quality benefit**.

**Decision:** `semantic_clustering_enabled: false` is now the default in `config/default.yaml`. It is opt-in only.

**When to enable:**
- Breaking news day with 5+ sources covering the same story (e.g., "OpenAI IPO" from TechCrunch, The Verge, Ars, Reuters, Wired)
- Feed volume consistently > 80 core articles/day
- You have a GPU-backed embedding model (not `qwen3-embedding:0.6b` on CPU)

**Opt-in methods:**
```bash
# Env var (one-off)
AI_DIGEST_embedding__semantic_clustering_enabled=true python3 scripts/daily.py

# Config (persistent)
# In config/default.yaml:
embedding:
  semantic_clustering_enabled: true
```

**Skip research embedding even when enabled:**
```bash
# Only embed core articles (32), skip research (176)
AI_DIGEST_embedding__semantic_clustering_enabled=true AI_DIGEST_SKIP_RESEARCH_EMBEDDING=true python3 scripts/daily.py
```

**Timeout bump for opted-in runs:**
The embedding HTTP timeout was bumped from 120s to 300s because `qwen3-embedding:0.6b` on CPU can take >2 minutes per batch when loaded. If you see `Read timed out` in logs, either reduce `embedding.batch_size` or switch to a faster embedding model.

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

---

## 13. Testing Pitfalls — Lazy SQLite Schema Initialization

If a module creates its own table **lazily** (e.g. `analysis/health.py` calls `_ensure_source_health_table()` on first use rather than in the global `_init_schema()`), test fixtures that only call `_ensure_schema()` will hit `sqlite3.OperationalError: no such table`.

**Symptom (CI failure after commit):**
```
ERROR tests/test_circuit_breaker.py::... - sqlite3.OperationalError: no such table: source_health
```

**Root cause:**
```python
# ❌ WRONG — main schema does NOT create source_health
from ai_news_digest.storage.sqlite_store import _conn, _ensure_schema
_ensure_schema()          # creates runs, topic_memory, entities, daily_reports...
                          # does NOT create source_health

# ✅ CORRECT — call the module's own lazy initializer
from ai_news_digest.analysis.health import _ensure_source_health_table
_ensure_source_health_table()
```

**Rule of thumb:** When writing test fixtures for SQLite-backed modules, check whether each table is created by the global schema init or by a module-level lazy function. Match the fixture to the actual creator.

---

## 14. API Design — Avoid Polymorphic Return Types in Shared Core Functions

`_agent_summarize()` originally returned `str` for daily mode and `dict` for weekly mode. This forced every caller to know which mode was active and handle the type differently — a classic footgun.

**Fix:** Always return the structured `dict`. Let the daily caller convert to text via `_structured_to_text()`, while the weekly caller uses the dict directly.

```python
# Before — polymorphic, callers must branch
result = _agent_summarize(..., weekly=is_weekly)
if is_weekly:
    payload = result        # dict
else:
    text = result           # str

# After — uniform return, caller decides conversion
result = _agent_summarize(..., weekly=is_weekly)   # always dict
if is_weekly:
    payload = result
else:
    text = _structured_to_text(result)
```

---

## 15. Architecture Patterns Introduced in v2.1 Refactor

### SourceAdapter Protocol
When the pipeline calls 4+ fetch functions with different signatures (RSS feeds list, page sources list, no args, `top_n` param), introduce a protocol:

```python
class SourceAdapter(Protocol):
    name: str
    def fetch(self) -> list[dict]: ...
```

Wrap each legacy fetcher in an adapter class (`RSSSourceAdapter`, `PageSourceAdapter`, etc.). The pipeline iterates uniformly:

```python
for adapter in adapters:
    articles = adapter.fetch()
    if adapter.name == "github_trending":
        research_articles.extend(articles)
    ...
```

**Benefit:** Eliminates duplicated error handling, circuit breaker logic, and metrics calls scattered across the pipeline.

### UnifiedStorage Facade
When storage is split across file-based JSON archives, SQLite for state/FTS, and in-memory topic history, create a single facade:

```python
class UnifiedStorage:
    def start_run(self) -> str: ...
    def save_daily_report(self, summary, articles, ...) -> dict[str, str]: ...
    def exclude_cross_day_duplicates(self, articles, days) -> tuple[list[dict], int]: ...
    def migrate(self) -> None: ...
```

Callers import one object (`storage = UnifiedStorage()`) and never need to know which backend handles which concern.

**Benefit:** Removes 3 separate import sites (`archive`, `sqlite_store`, `topic_memory`) and makes testing easier — the entire storage layer can be mocked at one boundary.
