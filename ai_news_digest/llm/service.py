from __future__ import annotations

import json
import re

import requests

from ai_news_digest.analysis.trends import format_trend_context
from ai_news_digest.config import get_llm_settings, logger

INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions|disregard\s+(all\s+)?(previous|prior)\s+instructions|forget\s+(all\s+)?(previous|prior)\s+instructions|new\s+instruction(s)?:|system\s*prompt\s*leak",
    re.IGNORECASE,
)

PROMPT_TEMPLATE = """You are an AI news curator. Given the following main news articles and research/builder signal articles about artificial intelligence, produce a daily digest.

Rules:
- Hacker News is enrichment-only. Do not list it as a standalone source.
- Research / Builder Signals must be its own separate section, not mixed into the main highlights.
- If weekly preview context is provided, include a short WEEKLY PREVIEW section near the end.
- Keep Research / Builder Signals to at most 5 items.
- If a research/builder signal has a subtype label in the article metadata, preserve it like [paper], [repo], [builder feed], or [product / launch].

Output format — use EXACTLY this structure:
Brief Rundown:
[your 2-3 sentence rundown here]

Trend Watch:
MAIN NEWS Trend Watch:
Heating Up:
- [Topic] — [why it is heating up]
Cooling Down:
- [Topic] — [why it is cooling down]

Highlights:
1. [Headline]
[1-2 sentence summary]
Source: [Publication Name] ([URL])

Also Worth Knowing:
- [Headline] | [Publication Name] ([URL])

Research / Builder Signals:
- [Subtype] [Headline] | [Publication Name] ([URL])
- [Subtype] [Headline] | [Publication Name] ([URL])

Weekly Preview:
- [brief preview bullet]
- [brief preview bullet]

If there is no meaningful trend context, omit TREND WATCH.
If there are no research/builder signals, omit RESEARCH / BUILDER SIGNALS.
If there is no weekly preview context, omit WEEKLY PREVIEW.

Trend context:
{trend_context}

Weekly preview context:
{weekly_preview}

Main articles:
{main_articles_json}

Research / Builder signal articles:
{research_articles_json}"""


def _sanitize(text: str) -> str:
    return INJECTION.sub('[redacted]', text)


def _serialize_articles(articles: list[dict]) -> str:
    return json.dumps(
        [
            {
                'title': _sanitize(a['title']),
                'summary': _sanitize(a.get('summary', ''))[:700],
                'content': _sanitize(a.get('content', ''))[:1500],
                'url': a['url'],
                'source': a['source'],
                'sources': a.get('sources', [a['source']]),
                'source_count': a.get('source_count', 1),
                'subtype': a.get('subtype', ''),
                'eli5': a.get('eli5', ''),
                'ranking_debug': a.get('ranking_debug', {}),
                'hacker_news': {
                    'points': a.get('hn_points', 0),
                    'comments': a.get('hn_comments', 0),
                    'discussion_url': a.get('hn_discussion_url', ''),
                },
                'ranking_score': a.get('ranking_score', 0),
            }
            for a in articles
        ],
        indent=2,
    )


def _build_prompt(main_articles: list[dict], research_articles: list[dict], trend_snapshot: dict | None = None, weekly_preview: str = '') -> str:
    trend_context = format_trend_context(trend_snapshot or {}) or 'No strong cross-day topic shifts detected.'
    return PROMPT_TEMPLATE.format(
        main_articles_json=_serialize_articles(main_articles),
        research_articles_json=_serialize_articles(research_articles),
        trend_context=trend_context,
        weekly_preview=weekly_preview or 'No weekly preview available.',
    )


def _ollama(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['ollama_host']}/api/generate",
        json={'model': settings['model'], 'prompt': prompt, 'stream': False},
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    return response.json().get('response', '').strip()


def _openai_compatible(prompt: str, settings: dict) -> str:
    provider = settings['provider']
    api_base = settings['api_base'] or {'openai': 'https://api.openai.com/v1', 'openrouter': 'https://openrouter.ai/api/v1'}[provider]
    headers = {'Authorization': f"Bearer {settings[f'{provider}_api_key']}", 'Content-Type': 'application/json'}
    if provider == 'openrouter':
        headers['HTTP-Referer'] = 'https://github.com/0xminion/ai-news-daily-digest'
        headers['X-Title'] = 'ai-news-daily-digest'
    response = requests.post(
        f"{api_base}/chat/completions",
        headers=headers,
        json={
            'model': settings['model'],
            'messages': [{'role': 'system', 'content': 'You create clean, accurate AI news digests.'}, {'role': 'user', 'content': prompt}],
            'temperature': 0.2,
            'max_tokens': settings['max_tokens'],
        },
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content'].strip()


def _anthropic(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['api_base'] or 'https://api.anthropic.com'}/v1/messages",
        headers={'x-api-key': settings['anthropic_api_key'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json={'model': settings['model'], 'max_tokens': settings['max_tokens'], 'temperature': 0.2, 'messages': [{'role': 'user', 'content': prompt}]},
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    data = response.json()
    return '\n'.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text').strip()


def summarize(main_articles: list[dict], trend_snapshot: dict | None = None, research_articles: list[dict] | None = None, weekly_preview: str = '') -> str:
    if not main_articles and not research_articles:
        return _quiet_day_message()
    research_articles = research_articles or []
    settings = get_llm_settings()
    prompt = _build_prompt(main_articles, research_articles, trend_snapshot, weekly_preview)
    logger.info(
        'Sending %d main articles and %d research articles to %s (%s)...',
        len(main_articles),
        len(research_articles),
        settings['provider'],
        settings['model'],
    )
    if settings['provider'] == 'ollama':
        result = _ollama(prompt, settings)
    elif settings['provider'] in {'openai', 'openrouter'}:
        result = _openai_compatible(prompt, settings)
    elif settings['provider'] == 'anthropic':
        result = _anthropic(prompt, settings)
    else:
        raise ValueError(f"Unsupported LLM provider '{settings['provider']}'")
    if not result:
        raise RuntimeError('LLM provider returned empty response')
    return result


def _quiet_day_message() -> str:
    return 'Brief Rundown:\nQuiet day in AI news — nothing major from our tracked sources in the last 24 hours.\n\nHighlights:\nNo highlights today.'
