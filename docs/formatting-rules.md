---
name: ai-news-digest
category: dev
description: >
  Standardize AI news digest formatting across any model or inference backend.
  Covers section structure, headline Markdown embed rules, Telegram MarkdownV2
  rendering, LLM output normalization, and the single formatting pipeline
  that all models must comply with.
---

# AI News Digest: Formatting & Structure Rules

> **One pipeline, any model.** kimi, minimax, gemma, claude, or gpt — all
> produce text that feeds into the same formatter. These rules keep the
> output consistent regardless of who's generating it.

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
| **minimax-m2.7:cloud** | Fast (~140 chars/sec). Standard timeout 120s is fine. |
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
| Also Worth Knowing truncation | **NEVER** — full headline |
| Subtype prefix | `[paper]`, `[repo]`, `[builder feed]`, `[product / launch]` |
| Telegram escaping | `_mdv2_escape()` on all text |
| HTML | Banned — stripped at two gates |
| Merged bullets | Split by `) - ` pattern |
| Section headings | Normalized to title case before parsing |
| Line boundaries | Preserved in `_strip_html` |
