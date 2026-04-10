from __future__ import annotations

RSS_FEEDS = [
    ("Wired", "https://www.wired.com/feed/rss"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    (
        "Reuters",
        "https://www.rss-bridge.org/bridge01/?action=display&bridge=FilterBridge&url=https%3A%2F%2Fwww.reuters.com%2Ftechnology%2F&filter=&filter_type=permit&format=Atom",
    ),
    ("VentureBeat", "https://venturebeat.com/feed/"),
]

PAGE_SOURCES = []

ORTHOGONAL_RSS_FEEDS = [
    ("arXiv AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("arXiv ML", "https://rss.arxiv.org/rss/cs.LG"),
    ("GitHub Blog AI/ML", "https://github.blog/ai-and-ml/feed/"),
]

GITHUB_TRENDING_ENABLED = True
GITHUB_TRENDING_SINCE = "daily"
GITHUB_TRENDING_LANGUAGE = ""
GITHUB_TRENDING_TOP_N = 3
