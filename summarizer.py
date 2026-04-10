import json
import re

import requests

from config import OLLAMA_TIMEOUT, get_llm_settings, logger

_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions"
    r"|disregard\s+(all\s+)?(previous|prior)\s+instructions"
    r"|forget\s+(all\s+)?(previous|prior)\s+instructions"
    r"|new\s+instruction(s)?:"
    r"|system\s*prompt\s*leak",
    re.IGNORECASE,
)


PROMPT_TEMPLATE = """You are an AI news curator. Given the following {n} articles about artificial intelligence, produce a daily digest with two sections:

1. BRIEF RUNDOWN: A 2-3 sentence paragraph hitting the big themes of the day. Be punchy and direct — no filler, no throat-clearing. Write like a sharp group chat message, not an essay.

2. MUST-KNOW HIGHLIGHTS: Select the 10 most important stories (or all if fewer than 10) and for each provide:
   - A clear headline
   - A 1-2 sentence summary — just the what and why it matters, nothing more
   - The source publication name and article URL exactly as provided

3. ALSO WORTH KNOWING: Select 5-10 additional stories worth a glance. For each provide ONLY:
   - The headline as-is
   - The source publication name and article URL exactly as provided
   No summaries for this section — just titles and links.

Prioritize: major product launches, policy/regulation changes, breakthrough research, significant business moves, and industry shifts. Deprioritize: opinion pieces, minor updates, and speculation. Ignore any articles that are not genuinely about AI.

Output format — use EXACTLY this structure:
BRIEF RUNDOWN:
[your rundown paragraph here]

HIGHLIGHTS:
1. [Headline]
[1-2 sentence summary]
Source: [Publication Name] - [URL]

2. [Headline]
[1-2 sentence summary]
Source: [Publication Name] - [URL]

(continue for up to 10 highlights)

ALSO WORTH KNOWING:
- [Headline] | [Publication Name] - [URL]
- [Headline] | [Publication Name] - [URL]

(continue for 5-10 more stories)

Articles:
{articles_json}"""


def _sanitize_for_prompt(text: str) -> str:
    return _INJECTION_PATTERNS.sub("[redacted]", text)


def _build_prompt(articles: list[dict]) -> str:
    articles_json = json.dumps(
        [
            {
                "title": _sanitize_for_prompt(a["title"]),
                "summary": _sanitize_for_prompt(a.get("summary", ""))[:700],
                "content": _sanitize_for_prompt(a.get("content", ""))[:1500],
                "url": a["url"],
                "source": a["source"],
            }
            for a in articles
        ],
        indent=2,
    )
    return PROMPT_TEMPLATE.format(n=len(articles), articles_json=articles_json)


def _ollama_generate(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['ollama_host']}/api/generate",
        json={"model": settings["model"], "prompt": prompt, "stream": False},
        timeout=settings["timeout"],
    )
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _openai_compatible_generate(prompt: str, settings: dict) -> str:
    provider = settings["provider"]
    api_base = settings["api_base"]
    if not api_base:
        api_base = {
            "openai": "https://api.openai.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }[provider]
    api_key = settings[f"{provider}_api_key"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/0xminion/ai-news-daily-digest"
        headers["X-Title"] = "ai-news-daily-digest"

    response = requests.post(
        f"{api_base}/chat/completions",
        headers=headers,
        json={
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": "You create clean, accurate AI news digests."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": settings["max_tokens"],
        },
        timeout=settings["timeout"],
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _anthropic_generate(prompt: str, settings: dict) -> str:
    response = requests.post(
        f"{settings['api_base'] or 'https://api.anthropic.com'}/v1/messages",
        headers={
            "x-api-key": settings["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings["model"],
            "max_tokens": settings["max_tokens"],
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=settings["timeout"],
    )
    response.raise_for_status()
    data = response.json()
    blocks = data.get("content", [])
    text_blocks = [block.get("text", "") for block in blocks if block.get("type") == "text"]
    return "\n".join(part for part in text_blocks if part).strip()


def summarize(articles: list[dict]) -> str:
    """Summarize articles using the configured LLM provider/model."""
    if not articles:
        return _quiet_day_message()

    settings = get_llm_settings()
    prompt = _build_prompt(articles)

    logger.info(
        "Sending %d articles to %s (%s)...",
        len(articles),
        settings["provider"],
        settings["model"],
    )

    try:
        if settings["provider"] == "ollama":
            result = _ollama_generate(prompt, settings)
        elif settings["provider"] in {"openai", "openrouter"}:
            result = _openai_compatible_generate(prompt, settings)
        elif settings["provider"] == "anthropic":
            result = _anthropic_generate(prompt, settings)
        else:
            raise ValueError(
                f"Unsupported LLM provider '{settings['provider']}'. Supported providers: ollama, openai, openrouter, anthropic."
            )

        if not result:
            logger.error("LLM provider returned empty response")
            raise RuntimeError("LLM provider returned empty response")

        logger.info("Summary generated (%d chars)", len(result))
        return result

    except requests.ConnectionError:
        logger.error("Cannot connect to %s provider endpoint", settings["provider"])
        raise
    except requests.Timeout:
        logger.error("%s timed out after %ss", settings["provider"], settings["timeout"])
        raise
    except requests.HTTPError as exc:
        logger.error("%s HTTP error: %s", settings["provider"], exc)
        raise


def _quiet_day_message() -> str:
    return (
        "BRIEF RUNDOWN:\n"
        "Quiet day in AI news — nothing major from our tracked sources "
        "in the last 24 hours. Check back tomorrow for the latest.\n\n"
        "HIGHLIGHTS:\n"
        "No highlights today."
    )
