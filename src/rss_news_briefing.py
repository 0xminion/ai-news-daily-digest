#!/usr/bin/env python3
"""RSS News Briefing — AI/Tech news from 7 sources, past 24h, noise-filtered.
   Enhanced: per-article summaries + brief rundown paragraph.
"""

import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import requests

# ── Config ────────────────────────────────────────────────────────────────────

FEEDS = {
    "Wired":           "https://www.wired.com/feed/rss",
    "TechCrunch":      "https://techcrunch.com/feed/",
    "The Verge":       "https://www.theverge.com/rss/index.xml",
    "Reuters":         "https://feeds.reuters.com/reuters/technologyNews",
    "Ars Technica":    "https://feeds.arstechnica.com/arstechnica/index",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "The Economist":   "https://www.economist.com/science-and-technology/rss.xml",
}

TITLE_DENYLIST = [
    re.compile(r, re.IGNORECASE) for r in [
        r"dealbook", r"newsletters", r"podcast", r"video", r"letter",
        r"press release", r"jobs\b", r"career", r"hiring",
        r"best of \w+ \d+", r"what('s| is) on \w+ \d+",
        r"sunday \w+", r"monday \w+", r"tuesday \w+", r"wednesday \w+",
        r"thursday \w+", r"friday \w+", r"saturday \w+",
        r"week in \w+", r"year in \w+", r"month in \w+",
        r"top \d+", r"\d+ \w+ gifts?", r"gift guide",
        r"sign up", r"subscribe", r"subscription",
        r"the download\b",          # MIT newsletter summary
    ]
]

TITLE_SECONDARY = [
    re.compile(r, re.IGNORECASE) for r in [
        r"review", r"preview", r"opinion", r"column", r"profile",
        r"interview with", r"q&a", r"ask", r"you asked",
        r"how to", r"what is", r"what's", r"understanding",
        r"explainer", r"guide", r"best practices", r"tips",
        r"openai says", r"google says", r"microsoft says",
        r"according to", r"might", r"may", r"could",
    ]
]

INTEREST_KEYWORDS = [
    re.compile(r, re.IGNORECASE) for r in [
        r"\bai\b", r"\bml\b", r"\bllm\b", r"\bgenai\b",
        r"artificial intelligence", r"machine learning", r"deep learning",
        r"neural network", r"large language model", r"generative ai",
        r"foundation model", r"multimodal", r"rag\b",
        r"openai", r"anthropic", r"deepmind", r"mistral ai", r"meta ai",
        r"llama\b", r"gpt[-\s]?\d", r"claude\b", r"gemini\b", r"chatgpt",
        r"copilot\b", r"cursor\b", r"perplexity",
        r"ai agent", r"agentic", r"reasoning model",
        r"quantum", r"nuclear fusion", r"nuclear fission",
        r"semiconductor", r"chip\b", r"silicon",
        r"spacex", r"rocket\b", r"starship", r"nasa\b", r"blue origin",
        r"climate tech", r"clean energy", r"solar cell",
        r"battery\b", r"energy storage", r"ev\b", r"electric vehicle",
        r"crispr", r"gene edit", r"mrna", r"biology",
        r"cybersecurity", r"ransomware", r"zero.day",
        r"robotics", r"humanoid", r"Boston Dynamics",
        r"autonomous vehicle", r"self.driving", r"waymo", r"tesla robotaxi",
        r"surveillance", r"privacy\b",
        r"apple intelligence", r"apple ai",
        r"samsung ai", r"galaxy ai",
        r"microsoft ai", r"windows ai",
        r"amazon ai", r"aws ai",
        r"meta llm", r"meta ai",
        r"nvidia\b", r"gpu\b",
        r"physics\b", r"chemistry\b", r"biology\b",
        r"astronomy\b", r"space telescope", r"james webb",
    ]
]

CUTOFF_HOURS    = 24
MAX_ARTICLES   = 20
TOP_N          = 10        # articles for brief rundown
FETCH_TIMEOUT  = 12       # seconds per article fetch
FETCH_WORKERS  = 6        # parallel article fetches

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_date(entry):
    for f in ("published_parsed", "updated_parsed", "created_parsed",
              "published", "updated"):
        val = getattr(entry, f, None)
        if not val:
            continue
        if isinstance(val, str):
            try:
                return parsedate_to_datetime(val)
            except Exception:
                continue
        if isinstance(val, tuple) and len(val) >= 9:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def is_ai_related(title, summary=""):
    text = f"{title} {summary}"[:1000]
    return any(k.search(text) for k in INTEREST_KEYWORDS)


def is_noisy(title):
    return any(p.search(title) for p in TITLE_DENYLIST)


def is_secondary(title):
    return any(p.search(title) for p in TITLE_SECONDARY)


def score_article(entry, primary_hits, secondary_hits):
    score = 0
    if primary_hits > 0:
        score += primary_hits * 10
    if secondary_hits > 0:
        score += secondary_hits * 3
    dt = parse_date(entry)
    if dt:
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age_hours < 6:
            score += 3
        elif age_hours < 12:
            score += 1
    url = getattr(entry, "link", "")[:200]
    if "utm_" not in url and "shareurl" not in url:
        score += 1
    return score


def count_hits(text, keywords):
    return sum(1 for k in keywords if k.search(text))


# ── Article content fetch + extractive summary ────────────────────────────────

def _extract_article_text(url):
    """Fetch article page and extract main paragraphs. Returns (text, error)."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HermesBot/1.0; +https://hermes.ai)",
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            return "", f"HTTP {resp.status_code}"
        resp.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        # Try common article containers
        article = (soup.find("article") or
                   soup.find("div", class_=re.compile(r"article|content|post|entry|story", re.I)) or
                   soup.find("main") or
                   soup.body)

        if not article:
            return "", "no article container found"

        # Collect paragraphs
        paras = []
        for p in article.find_all("p"):
            txt = p.get_text(separator=" ", strip=True)
            if len(txt) > 60:          # skip nav/UI blurb
                paras.append(txt)

        if not paras:
            return "", "no paragraphs found"

        # Join first 8 paragraphs for summarisation source
        raw = " ".join(paras[:8])
        return raw, None

    except requests.exceptions.Timeout:
        return "", "timeout"
    except requests.exceptions.SSLError:
        return "", "ssl error"
    except Exception as e:
        return "", str(e)[:60]


def _extractive_summary(text, num_sentences=2):
    """Simple extractive summariser: picks the 2 longest non-redundant sentences."""
    # Split into sentences (naïve but functional)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Score by length (word count), filter very short ones
    scored = [(s.strip(), len(s.split())) for s in sentences if len(s.split()) >= 8]
    if not scored:
        return text[:300].rsplit(" ", 1)[0] + "…"

    # Pick top-N longest
    top = sorted(scored, key=lambda x: -x[1])[:num_sentences]
    # Restore original order
    ordered = sorted(top, key=lambda x: sentences.index(x[0]) if x[0] in sentences else 999)
    return " ".join(s[0] for s in ordered)


def _summarise_article(url, title, rss_summary, fallback_max=300):
    """Return a 1-2 sentence summary for an article."""
    raw, err = _extract_article_text(url)
    if err or not raw:
        # Fall back to RSS summary, trimmed
        summary = re.sub(r"<[^>]+>", " ", rss_summary)
        summary = re.sub(r"\s+", " ", summary).strip()
        if not summary:
            return title or "[untitled]"
        return summary[:fallback_max].rsplit(" ", 1)[0].rstrip(",;") + "…"

    return _extractive_summary(raw, num_sentences=2)


# ── Brief rundown generator ───────────────────────────────────────────────────

def _make_rundown(articles):
    """Synthesise a longer contextual paragraph from the top articles."""
    if not articles:
        return "No significant AI or tech news today."

    top = articles[:12]

    # Regex-based category detection — use a small keyword set directly
    AI_RE    = re.compile(r"(?i)(ai|ml|llm|artificial intelligence|neural|openai|anthropic|deepmind|gpt|claude|gemini|llama|agent|copilot|perplexity)\b", re.I)
    CHIP_RE  = re.compile(r"(?i)(chip|silicon|semiconductor|nvidia|gpu|arm\b)", re.I)
    SPACE_RE = re.compile(r"(?i)(spacex|rocket|starship|nasa|blue origin|astronomy|james webb)", re.I)
    ROBOT_RE = re.compile(r"(?i)(robot|humanoid|boston dynamic|autonomous vehicle|self.driving|waymo|tesla robotaxi)", re.I)

    ai_news       = [a for a in top if AI_RE.search(a["title"])]
    chip_news     = [a for a in top if CHIP_RE.search(a["title"])]
    space_news    = [a for a in top if SPACE_RE.search(a["title"])]
    robotics_news = [a for a in top if ROBOT_RE.search(a["title"])]

    # ── Build entity list ────────────────────────────────────────────────────
    def get_orgs(art_list):
        orgs = set()
        for a in art_list:
            t = a["title"].lower()
            if "openai"    in t or "gpt-"    in t or "chatgpt"  in t: orgs.add("OpenAI")
            if "anthropic" in t or "claude"  in t:                 orgs.add("Anthropic")
            if "google"    in t or "gemini"   in t or "deepmind" in t: orgs.add("Google")
            if "meta"     in t or "llama"    in t:                  orgs.add("Meta")
            if "microsoft" in t or "copilot" in t:                 orgs.add("Microsoft")
            if "apple"    in t or "samsung"  in t:                  orgs.add("Apple/Samsung")
            if "nvidia"   in t or "gpu"       in t:                  orgs.add("Nvidia/GPU")
            if "arm"      in t:                                         orgs.add("Arm")
            if "amazon"   in t:                                         orgs.add("Amazon")
            if "sony"     in t or "honda"     in t:                  orgs.add("Sony/Honda")
            if "mozilla"  in t:                                         orgs.add("Mozilla")
            if "pentagon" in t or "doctrine"  in t or "defense"   in t: orgs.add("the Pentagon")
        return orgs

    ai_orgs      = get_orgs(ai_news)
    chip_orgs    = get_orgs(chip_news)
    space_orgs   = get_orgs(space_news)
    robotics_orgs= get_orgs(robotics_news)

    sentences = []

    # ── AI paragraph ─────────────────────────────────────────────────────────
    if ai_news:
        org_str = ", ".join(sorted(ai_orgs)[:5])
        ai_count = len(ai_news)
        sources  = ", ".join(sorted({a["source"] for a in ai_news}))
        if ai_count == 1:
            sentences.append(f"{ai_news[0]['title']} ({sources}) dominated the AI beat.")
        else:
            sentences.append(
                f"AI remained the dominant theme, with {ai_count} stories centring on "
                f"{org_str}. Coverage spanned {sources}, framing the moment as a pivotal "
                f"turn in the industry's direction."
            )

    # ── Chips/silicon paragraph ─────────────────────────────────────────────
    if chip_news:
        org_str = ", ".join(sorted(chip_orgs)[:4])
        chip_count = len(chip_news)
        sources    = ", ".join(sorted({a["source"] for a in chip_news}))
        chip_piece = "" if chip_count == 1 else "s"
        sentences.append(
            f"The silicon story ran hot alongside it — {chip_count} piece{chip_piece} on advances "
            f"in chip design and AI silicon from {org_str} ({sources}). "
            f"{chip_news[0]['title']} set the tone."
        )

    # ── Space / deep tech ─────────────────────────────────────────────────────
    if space_news:
        org_str  = ", ".join(sorted(space_orgs)[:3])
        src_str  = ", ".join(sorted({a["source"] for a in space_news}))
        sentences.append(f"Beyond the AI layer, {org_str} featured in {len(space_news)} "
                         f"stories ({src_str}), keeping space and deep-tech on the radar.")

    # ── Robotics / autonomy ──────────────────────────────────────────────────
    if robotics_news:
        org_str  = ", ".join(sorted(robotics_orgs)[:3])
        src_str  = ", ".join(sorted({a["source"] for a in robotics_news}))
        sentences.append(f"Robotics and autonomy surfaced in {len(robotics_news)} items "
                         f"({org_str}; {src_str}), reflecting continued investment momentum.")

    if not sentences:
        total    = len(top)
        sources  = len({a["source"] for a in top})
        sentences.append(f"An active day with {total} stories across {sources} sources — "
                         f"no single narrative dominated.")

    return " ".join(sentences)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=CUTOFF_HOURS)

    all_articles = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[{source}] fetch error: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            title   = getattr(entry, "title",   "") or ""
            link    = getattr(entry, "link",    "") or ""
            summary = getattr(entry, "summary", "") or ""
            summary = re.sub(r"<[^>]+>", " ", summary)
            summary = re.sub(r"\s+", " ", summary).strip()

            if is_noisy(title):
                continue

            dt = parse_date(entry)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt and dt < cutoff:
                continue

            if not is_ai_related(title, summary):
                continue

            primary   = count_hits(f"{title} {summary}", INTEREST_KEYWORDS)
            secondary = count_hits(f"{title} {summary}", TITLE_SECONDARY)
            score     = score_article(entry, primary, secondary)
            all_articles.append({
                "source":  source,
                "title":   title,
                "link":    link,
                "summary": summary[:250],
                "score":   score,
                "primary": primary,
                "dt":      dt,
            })

    if not all_articles:
        print("No articles found for today.")
        return

    all_articles.sort(key=lambda a: (-a["primary"], -a["score"],
                                      a["dt"] or datetime.min))

    primary_articles   = [a for a in all_articles if a["primary"] >= 3][:MAX_ARTICLES]
    secondary_articles = [a for a in all_articles if a not in primary_articles][:10]

    # ── Fetch per-article summaries in parallel ─────────────────────────────
    articles_for_summary = primary_articles[:TOP_N]

    def fetch_one(a):
        s = _summarise_article(a["link"], a["title"], a["summary"])
        return a, s

    article_summaries = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(fetch_one, a): a for a in articles_for_summary}
        for future in as_completed(futures):
            a, s = future.result()
            article_summaries[a["link"]] = s

    # ── Output ───────────────────────────────────────────────────────────────
    print(f"AI NEWS BRIEFING — {now.strftime('%A, %B %d, %Y')}")
    print(f"{'─'*64}")
    print(f"{len(all_articles)} articles found across {len(FEEDS)} sources (past {CUTOFF_HOURS}h)")
    print()

    # Brief rundown paragraph
    print("BRIEF RUNDOWN")
    print(f"{'─'*64}")
    rundown = _make_rundown(primary_articles)
    print(rundown)
    print()

    # Top N with summaries
    print(f"TOP {len(articles_for_summary)} STORIES")
    print(f"{'─'*64}")
    for i, a in enumerate(articles_for_summary, 1):
        age = ""
        if a["dt"]:
            age_h = (now - a["dt"]).total_seconds() / 3600
            if age_h < 1:
                age = f" ({age_h*60:.0f}m ago)"
            else:
                age = f" ({age_h:.1f}h ago)"

        print(f"{i}. [{a['source']}{age}]")
        print(f"   {a['title']}")
        print(f"   {a['link']}")
        print(f"   → {article_summaries.get(a['link'], a['summary'][:200])}")
        print()

    # More stories (secondary)
    if secondary_articles:
        print(f"MORE STORIES ({len(secondary_articles)})")
        print(f"{'─'*64}")
        for a in secondary_articles[:10]:
            age = ""
            if a["dt"]:
                age_h = (now - a["dt"]).total_seconds() / 3600
                if age_h < 1:
                    age = f" ({age_h*60:.0f}m ago)"
                else:
                    age = f" ({age_h:.1f}h ago)"
            print(f"[{a['source']}{age}] {a['title']}")
            print(f"  {a['link']}")
        print()


if __name__ == "__main__":
    main()
