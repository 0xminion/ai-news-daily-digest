import json

import requests

from config import OLLAMA_MODEL, OLLAMA_HOST, OLLAMA_TIMEOUT, logger


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


def summarize(articles: list[dict]) -> str:
    """Summarize articles using the configured LLM (Ollama).

    This function is the model swappability boundary — to switch to Claude,
    GPT, or another provider, change only the implementation here.
    """
    if not articles:
        return _quiet_day_message()

    articles_json = json.dumps(
        [
            {
                "title": a["title"],
                "summary": a["summary"][:500],
                "url": a["url"],
                "source": a["source"],
            }
            for a in articles
        ],
        indent=2,
    )

    prompt = PROMPT_TEMPLATE.format(n=len(articles), articles_json=articles_json)

    try:
        logger.info(
            f"Sending {len(articles)} articles to Ollama ({OLLAMA_MODEL})..."
        )
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        result = data.get("response", "").strip()

        if not result:
            logger.error("Ollama returned empty response")
            raise RuntimeError("Ollama returned empty response")

        logger.info(f"Summary generated ({len(result)} chars)")
        return result

    except requests.ConnectionError:
        logger.error(
            f"Cannot connect to Ollama at {OLLAMA_HOST}. "
            f"Is Ollama running? Try: ollama serve"
        )
        raise
    except requests.Timeout:
        logger.error(
            f"Ollama timed out after {OLLAMA_TIMEOUT}s. "
            f"The model may be too slow or too many articles were sent."
        )
        raise
    except requests.HTTPError as e:
        logger.error(f"Ollama HTTP error: {e}")
        raise


def _quiet_day_message() -> str:
    return (
        "BRIEF RUNDOWN:\n"
        "Quiet day in AI news — nothing major from our tracked sources "
        "in the last 24 hours. Check back tomorrow for the latest.\n\n"
        "HIGHLIGHTS:\n"
        "No highlights today."
    )
