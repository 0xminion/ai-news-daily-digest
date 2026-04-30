from __future__ import annotations

import json
import re
from pathlib import Path

import requests

from ai_news_digest.config import get_llm_settings, logger
from ai_news_digest.utils.retry import with_retry

INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions|disregard\s+(all\s+)?(previous|prior)\s+instructions|forget\s+(all\s+)?(previous|prior)\s+instructions|new\s+instruction(s)?:|system\s*prompt\s*leak",
    re.IGNORECASE,
)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'

# Expected top-level keys in structured output
REQUIRED_DIGEST_KEYS = {'brief_rundown', 'highlights'}
OPTIONAL_DIGEST_KEYS = {'also_worth_knowing', 'research_builder_signals'}

# Token guard constants — rough ~4 chars/token for English
# Leave headroom for system instructions, JSON overhead, and response
_CHARS_PER_TOKEN = 4
_SYSTEM_OVERHEAD_TOKENS = 512
# Default model family token limits.
# Unknown models are treated as unsupported for this project unless explicitly
# mapped here or inferred from a 200k+ family match.
_MIN_REQUIRED_CONTEXT_TOKENS = 200000
_DEFAULT_CONTEXT_LIMITS = {
    'claude-sonnet': 200000,
    'claude-3.5': 200000,
    'claude-3': 200000,
    'gpt-4o-mini': 128000,
    'gpt-4o': 128000,
    'ollama': 256000,
    'minimax': 256000,
    'kimi': 256000,
    'default': 8192,
}
_MAX_DAILY_ARTICLES = 100


def _estimate_tokens(text: str) -> int:
    """Return rough token estimate using character ratio (no tiktoken needed)."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _context_limit_for_model(model: str) -> int:
    """Infer context window from model name, falling back to a conservative default."""
    model_lower = (model or '').lower()
    for key, limit in _DEFAULT_CONTEXT_LIMITS.items():
        if key != 'default' and key in model_lower:
            return limit
    return _DEFAULT_CONTEXT_LIMITS['default']


def _require_supported_context_window(model: str, declared_context_limit: int | None = None) -> int:
    """Reject models that do not meet the project's 200k+ context requirement."""
    context_limit = declared_context_limit or _context_limit_for_model(model)
    if context_limit < _MIN_REQUIRED_CONTEXT_TOKENS:
        raise ValueError(
            'ai-news-daily-digest requires a model with at least '
            f'{_MIN_REQUIRED_CONTEXT_TOKENS} tokens of context; '
            f"'{model}' was inferred at {context_limit}."
        )
    return context_limit


def _truncate_articles_to_fit(
    main_articles: list[dict],
    research_articles: list[dict],
    template: str,
    max_tokens: int,
) -> tuple[list[dict], list[dict]]:
    """Progressively reduce article detail until prompt fits in context window."""
    overhead = template.replace('{{main_articles_json}}', '').replace('{{research_articles_json}}', '')
    overhead_tokens = _estimate_tokens(overhead) + _SYSTEM_OVERHEAD_TOKENS
    remaining_tokens = max(0, max_tokens - overhead_tokens)
    remaining_chars = remaining_tokens * _CHARS_PER_TOKEN

    def _serialize_truncated(main: list[dict], research: list[dict], content_len: int) -> str:
        def _trim(a: dict) -> dict:
            return {
                'title': a.get('title', '')[:200],
                'summary': (a.get('summary', '') or '')[:content_len],
                'content': '',
                'url': a.get('url', ''),
                'source': a.get('source', ''),
                'sources': a.get('sources', [a.get('source', '')]),
                'source_count': a.get('source_count', 1),
                'subtype': a.get('subtype', ''),
                'eli5': a.get('eli5', ''),
                'ranking_score': a.get('ranking_score', 0),
                'hacker_news': {
                    'points': a.get('hn_points', 0),
                    'comments': a.get('hn_comments', 0),
                    'discussion_url': a.get('hn_discussion_url', ''),
                },
            }
        return json.dumps([_sanitize_dict(_trim(a)) for a in main + research], indent=2)

    # Binary search for max summary length per article
    low, high = 0, 1500
    best_content_len = 0
    while low <= high:
        mid = (low + high) // 2
        serialized = _serialize_truncated(main_articles, research_articles, mid)
        if len(serialized) <= remaining_chars:
            best_content_len = mid
            low = mid + 1
        else:
            high = mid - 1

    # Ensure at least some context remains
    best_content_len = max(best_content_len, 100)

    # If still too large, drop articles from the end
    while True:
        serialized = _serialize_truncated(main_articles, research_articles, best_content_len)
        if len(serialized) <= remaining_chars:
            break
        # Prefer dropping from research first, then main tail
        if research_articles:
            research_articles = research_articles[:-1]
        elif len(main_articles) > 5:
            main_articles = main_articles[:-1]
        else:
            # Still overflow with tiny main set — increase truncation
            best_content_len = max(0, best_content_len - 50)
        if best_content_len <= 0 and len(main_articles) <= 5:
            logger.error('Prompt too large even with minimal articles — sending as-is; LLM may reject')
            break
    return main_articles, research_articles


def _sanitize(text: str) -> str:
    return INJECTION.sub('[redacted]', text)


def _sanitize_dict(d: dict) -> dict:
    return {k: _sanitize(v) if isinstance(v, str) else v for k, v in d.items()}


def _load_prompt_template(name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = PROMPTS_DIR / f'{name}.md'
    if not path.exists():
        raise FileNotFoundError(f'Prompt template not found: {path}')
    return path.read_text(encoding='utf-8')


def _serialize_articles(articles: list[dict]) -> str:
    """Serialize articles for LLM prompt."""
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


def _build_prompt(main_articles: list[dict], research_articles: list[dict], max_tokens: int | None = None) -> str:
    """Build prompt with double-brace markers so article JSON never collides with template tokens."""
    template = _load_prompt_template('daily')
    if max_tokens is not None:
        # Token guard: cap articles before serializing
        main_articles, research_articles = _truncate_articles_to_fit(
            main_articles,
            research_articles,
            template,
            max_tokens,
        )
    return (
        template
        .replace('{{main_articles_json}}', _serialize_articles(main_articles))
        .replace('{{research_articles_json}}', _serialize_articles(research_articles))
    )


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    return json.loads(cleaned)


def _validate_digest(data: dict) -> dict:
    """Validate and normalize structured digest output."""
    if not isinstance(data, dict):
        raise ValueError(f'Expected dict, got {type(data).__name__}')

    missing = REQUIRED_DIGEST_KEYS - set(data.keys())
    if missing:
        raise ValueError(f'Missing required keys: {missing}')

    # Normalize highlights to list
    if isinstance(data.get('highlights'), str):
        data['highlights'] = [{'headline': data['highlights'], 'summary': '', 'source': '', 'url': ''}]

    # Ensure lists for array fields
    for key in ['also_worth_knowing', 'research_builder_signals']:
        if key not in data:
            data[key] = []
        elif not isinstance(data[key], list):
            data[key] = [data[key]]

    return data


def _structured_to_text(data: dict) -> str:
    """Convert structured JSON digest back to text format for backward compat."""
    lines = []

    lines.append('Brief Rundown:')
    lines.append(data.get('brief_rundown', ''))
    lines.append('')

    # Highlights
    lines.append('Highlights:')
    for idx, h in enumerate(data.get('highlights', []), 1):
        headline = h.get('headline', '')
        url = h.get('url', '')
        if url:
            lines.append(f"{idx}. [{headline}]({url})")
        else:
            lines.append(f"{idx}. {headline}")
        if h.get('summary'):
            lines.append(h['summary'])
        if h.get('source'):
            lines.append(f"Source: {h['source']}")
        lines.append('')

    # Also worth knowing
    also = data.get('also_worth_knowing', [])
    if also:
        lines.append('Also Worth Knowing:')
        for item in also:
            title = item.get('headline', '')
            source = item.get('source', '')
            url = item.get('url', '')
            if url:
                lines.append(f"- [{title}]({url}) ({source})")
            else:
                lines.append(f"- {title} ({source})")
        lines.append('')

    # Research signals
    research = data.get('research_builder_signals', [])
    if research:
        lines.append('Research / Builder Signals:')
        for item in research:
            # Strip brackets from subtype if LLM included them (e.g. "[paper]" → "paper")
            subtype = (item.get('subtype') or '').strip('[]')
            headline = item.get('headline', '')
            source = item.get('source', '')
            url = item.get('url', '')
            prefix = f"[{subtype}] " if subtype else ''
            if url:
                lines.append(f"- {prefix}[{headline}]({url}) ({source})")
            else:
                lines.append(f"- {prefix}{headline} ({source})")
        lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Weekly prompt builder
# ---------------------------------------------------------------------------

REQUIRED_WEEKLY_KEYS = {'executive_summary', 'highlights_of_the_week'}


def _build_weekly_prompt(archives: list[dict], window_days: int = 7, max_tokens: int | None = None) -> str:
    template = _load_prompt_template('weekly')
    overhead = template.replace('{{window_days}}', '').replace('{{archives_json}}', '')
    overhead_tokens = _estimate_tokens(overhead) + _SYSTEM_OVERHEAD_TOKENS
    if max_tokens is not None:
        remaining_chars = max(0, max_tokens - overhead_tokens) * _CHARS_PER_TOKEN
        serialized = json.dumps(archives, indent=2, ensure_ascii=False)
        # Shrink archive detail progressively: truncate article summaries to 200, then drop articles
        truncating_archives = archives
        while len(serialized) > remaining_chars and truncating_archives:
            if len(truncating_archives) > 3:
                truncating_archives = truncating_archives[:-1]
            else:
                # Summarize each remaining archive down to top 5 articles
                shrunk = []
                for payload in truncating_archives:
                    payload = dict(payload)
                    payload['articles'] = [
                        {'title': a.get('title', '')[:200], 'url': a.get('url', ''), 'source': a.get('source', '')}
                        for a in payload.get('articles', [])[:5]
                    ]
                    shrunk.append(payload)
                truncating_archives = shrunk
                remaining_chars = max(0, remaining_chars - 500)  # progressively accept smaller output
            serialized = json.dumps(truncating_archives, indent=2, ensure_ascii=False)
            if remaining_chars <= 5000:
                break
        return (
            template
            .replace('{{window_days}}', str(window_days))
            .replace('{{archives_json}}', serialized)
        )
    return (
        template
        .replace('{{window_days}}', str(window_days))
        .replace('{{archives_json}}', json.dumps(archives, indent=2, ensure_ascii=False))
    )


def _validate_weekly(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError(f'Expected dict, got {type(data).__name__}')
    missing = REQUIRED_WEEKLY_KEYS - set(data.keys())
    if missing:
        raise ValueError(f'Missing required keys: {missing}')
    # Ensure list fields
    for key in ('trending_directions', 'research_focus',
                'research_builder_signals', 'missed_but_emerging'):
        if key not in data:
            data[key] = []
        elif not isinstance(data[key], list):
            data[key] = [data[key]]
    return data


# ---------------------------------------------------------------------------
# LLM provider calls with retry
# ---------------------------------------------------------------------------

@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError))
def _ollama(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['ollama_host']}/api/generate",
        json={'model': settings['model'], 'prompt': prompt, 'stream': False},
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    result = response.json().get('response', '').strip()
    if not result:
        raise RuntimeError('Ollama returned empty response')
    return result


@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError, KeyError))
def _openai_compatible(prompt: str, settings: dict) -> str:
    provider = settings['provider']
    api_base = settings['api_base'] or {'openai': 'https://api.openai.com/v1', 'openrouter': 'https://openrouter.ai/api/v1'}[provider]
    headers = {'Authorization': f"Bearer {settings[f'{provider}_api_key']}", 'Content-Type': 'application/json'}
    if provider == 'openrouter':
        headers['HTTP-Referer'] = 'https://github.com/0xminion/ai-news-daily-digest'
        headers['X-Title'] = 'ai-news-daily-digest'
    body = {
        'model': settings['model'],
        'messages': [
            {'role': 'system', 'content': 'You create clean, accurate AI news digests. Always respond with valid JSON.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': settings.get('temperature', 0.2),
        'max_tokens': settings['max_tokens'],
    }
    # Only request structured JSON when the endpoint supports it.
    # Some OpenAI-compatible endpoints (e.g. Nous Research) do not support
    # response_format, so we try without it on the first 400 error.
    body['response_format'] = {'type': 'json_object'}
    response = requests.post(
        f"{api_base}/chat/completions",
        headers=headers,
        json=body,
        timeout=settings['timeout'],
    )
    if response.status_code == 400 and 'response_format' in body:
        # Retry without structured output request
        del body['response_format']
        response = requests.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=body,
            timeout=settings['timeout'],
        )
    response.raise_for_status()
    data = response.json()
    choice = data.get('choices', [{}])[0]
    if not choice or not isinstance(choice, dict):
        raise RuntimeError(f'OpenAI returned unexpected structure: {data.keys()}')
    message = choice.get('message', {})
    if not message or 'content' not in message:
        raise RuntimeError(f'OpenAI response missing content: {choice.keys()}')
    result = message['content'].strip()
    # Some reasoning models (e.g. kimi-k2.6) return empty content and put
    # the response in the reasoning field.
    if not result and message.get('reasoning'):
        result = message['reasoning'].strip()
    if not result:
        raise RuntimeError('OpenAI returned empty response')
    return result


@with_retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(requests.RequestException, RuntimeError, json.JSONDecodeError))
def _anthropic(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['api_base'] or 'https://api.anthropic.com'}/v1/messages",
        headers={'x-api-key': settings['anthropic_api_key'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json={
            'model': settings['model'],
            'max_tokens': settings['max_tokens'],
            'temperature': settings.get('temperature', 0.2),
            'system': 'You create clean, accurate AI news digests. Always respond with valid JSON.',
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=settings['timeout'],
    )
    response.raise_for_status()
    data = response.json()
    result = '\n'.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text').strip()
    if not result:
        raise RuntimeError('Anthropic returned empty response')
    return result


# ---------------------------------------------------------------------------
# Agent-native summarization — no external LLM API required
# ---------------------------------------------------------------------------

class AgentSummarizationRequired(Exception):
    """Raised when the agent provider is active and a human/agent must generate the summary."""

    def __init__(self, prompt_path: str, response_path: str, prompt_text: str = '') -> None:
        self.prompt_path = prompt_path
        self.response_path = response_path
        self.prompt_text = prompt_text
        super().__init__(
            f"Agent summarization required. Prompt saved to {prompt_path}. "
            f"Generate the structured JSON digest and save it to {response_path}, then re-run."
        )


def _agent_summarize(
    prompt: str,
    main_articles: list[dict],
    research_articles: list[dict],
    weekly: bool = False,
) -> dict:
    """Agent-native mode: write prompt to disk, check for agent-written response.

    Two automation paths are supported:
    1. AGENT_DIGEST_JSON env var — pass the raw JSON string directly.
    2. File handshake — write prompt to data/agent_prompt.json, wait for
       data/agent_response.json (created by the agent or user).

    Returns the validated structured dict regardless of weekly/daily mode.
    Callers are responsible for converting to text if needed.
    """
    import os

    from ai_news_digest.config.yaml_loader import get_data_dir

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = data_dir / 'agent_prompt.json'
    response_path = data_dir / 'agent_response.json'

    # Path 1: env var (useful for wrappers and cron jobs)
    env_json = os.environ.get('AGENT_DIGEST_JSON')
    if env_json:
        try:
            parsed = _extract_json(env_json)
            if weekly:
                validated = _validate_weekly(parsed)
            else:
                validated = _validate_digest(parsed)
            return validated
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning('AGENT_DIGEST_JSON invalid (%s), falling back to file mode', exc)

    # Path 2: file handshake
    # Save structured prompt so the agent has everything it needs
    prompt_data = {
        'mode': 'weekly' if weekly else 'daily',
        'instruction': (
            'You are an AI news curator. Generate a structured digest JSON '
            'matching the schema below. Do not include HTML. Use bare URLs or '
            'Markdown [text](url) links. Return ONLY valid JSON.'
        ),
        'prompt_text': prompt,
        'main_articles': [
            {'title': a.get('title', ''), 'url': a.get('url', ''), 'source': a.get('source', '')}
            for a in main_articles
        ],
        'research_articles': [
            {
                'title': a.get('title', ''),
                'url': a.get('url', ''),
                'source': a.get('source', ''),
                'subtype': a.get('subtype', ''),
            }
            for a in research_articles
        ],
        'schema': {
            'brief_rundown': '2-3 sentence overview',
            'highlights': [
                {
                    'headline': '...',
                    'summary': '1-2 sentences',
                    'source': 'Publication Name',
                    'url': 'https://...',
                    'why_it_matters': '1 sentence',
                }
            ],
            'also_worth_knowing': [
                {'headline': '...', 'source': '...', 'url': '...'}
            ],
            'research_builder_signals': [
                {
                    'headline': '...',
                    'source': '...',
                    'url': '...',
                    'subtype': 'paper | repo | builder feed | product / launch',
                }
            ],
        },
    }
    prompt_path.write_text(json.dumps(prompt_data, indent=2, ensure_ascii=False), encoding='utf-8')

    # Check if agent already wrote response
    if response_path.exists():
        try:
            raw = response_path.read_text(encoding='utf-8')
            parsed = _extract_json(raw)
            if weekly:
                validated = _validate_weekly(parsed)
            else:
                validated = _validate_digest(parsed)
            response_path.unlink()
            return validated
        except Exception as exc:
            logger.warning('Agent response file invalid (%s), waiting for new response', exc)

    raise AgentSummarizationRequired(str(prompt_path), str(response_path), prompt)


# ---------------------------------------------------------------------------
# Main summarize function
# ---------------------------------------------------------------------------

def summarize(main_articles: list[dict], research_articles: list[dict] | None = None) -> str:
    if not main_articles and not research_articles:
        return _quiet_day_message()
    research_articles = research_articles or []
    settings = get_llm_settings()

    if settings['provider'] == 'agent':
        prompt = _build_prompt(main_articles, research_articles, max_tokens=None)
        result = _agent_summarize(prompt, main_articles, research_articles)
        return _structured_to_text(result)

    context_limit = _require_supported_context_window(settings['model'], settings.get('context_limit'))
    # Reserve tokens for response generation + prompt overhead
    max_prompt_tokens = max(0, context_limit - settings['max_tokens'] - _SYSTEM_OVERHEAD_TOKENS)
    prompt = _build_prompt(main_articles, research_articles, max_tokens=max_prompt_tokens)
    logger.info(
        'Sending %d main articles and %d research articles to %s (%s)...',
        len(main_articles),
        len(research_articles),
        settings['provider'],
        settings['model'],
    )

    if settings['provider'] == 'ollama':
        raw = _ollama(prompt, settings)
    elif settings['provider'] in {'openai', 'openrouter'}:
        raw = _openai_compatible(prompt, settings)
    elif settings['provider'] == 'anthropic':
        raw = _anthropic(prompt, settings)
    else:
        raise ValueError(f"Unsupported LLM provider '{settings['provider']}'")

    # Parse structured JSON output
    try:
        parsed = _extract_json(raw)
        validated = _validate_digest(parsed)
        logger.info('Structured digest parsed successfully (%d highlights, %d research signals)',
                    len(validated.get('highlights', [])),
                    len(validated.get('research_builder_signals', [])))
        # Save structured JSON alongside text for archive
        return _structured_to_text(validated)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning('Structured parse failed (%s), falling back to raw text', exc)
        # Fallback: return raw text for backward-compatible section parsing
        if not raw:
            raise RuntimeError('LLM provider returned empty response')
        return raw


def _quiet_day_message() -> str:
    return 'Brief Rundown:\nQuiet day in AI news — nothing major from our tracked sources in the last 24 hours.\n\nHighlights:\nNo highlights today.'


def summarize_weekly(archives: list[dict], window_days: int = 7, use_llm: bool = True) -> dict:
    """Generate weekly payload via LLM if enabled, else use deterministic fallback.

    Archives should be recent daily payload dicts (with articles, trends, etc).
    Returns a dict matching the weekly.md structure.
    """
    if not archives:
        return {
            'window_days': window_days,
            'executive_summary': 'No archives available for this week.',
            'highlights_of_the_week': [],
            'trending_directions': [],
            'research_focus': [],
            'thinking_prompts': [],
            'research_builder_signals': [],
            'missed_but_emerging': [],
        }
    if not use_llm:
        raise RuntimeError('Deterministic weekly fallback is removed; use_llm must be True')
    settings = get_llm_settings()
    context_limit = _require_supported_context_window(settings['model'], settings.get('context_limit'))
    # Reserve tokens for response generation + prompt overhead
    max_prompt_tokens = max(0, context_limit - settings['max_tokens'] - _SYSTEM_OVERHEAD_TOKENS)
    prompt = _build_weekly_prompt(archives, window_days=window_days, max_tokens=max_prompt_tokens)
    logger.info(
        'Sending %d archive days to weekly prompt (%s / %s)...',
        len(archives),
        settings['provider'],
        settings['model'],
    )
    if settings['provider'] == 'ollama':
        raw = _ollama(prompt, settings)
    elif settings['provider'] in {'openai', 'openrouter'}:
        raw = _openai_compatible(prompt, settings)
    elif settings['provider'] == 'anthropic':
        raw = _anthropic(prompt, settings)
    elif settings['provider'] == 'agent':
        return _agent_summarize(prompt, [], [], weekly=True)
    else:
        raise ValueError(f"Unsupported LLM provider '{settings['provider']}'")
    try:
        parsed = _extract_json(raw)
        validated = _validate_weekly(parsed)
        logger.info('Weekly digest parsed successfully')
        return validated
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning('Weekly structured parse failed (%s), falling back to deterministic build', exc)
        # If LLM fails to return valid JSON, we could fall back to deterministic.
        # For now, propagate a clear error so the caller knows the LLM failed.
        raise RuntimeError(f'Weekly LLM failed and no deterministic fallback was configured: {exc}')
