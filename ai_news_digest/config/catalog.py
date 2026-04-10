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

PAGE_SOURCES = [
    {"name": "Fortune", "url": "https://fortune.com/section/artificial-intelligence/", "extractor": "fortune_ai"},
]

ORTHOGONAL_RSS_FEEDS = [
    ("arXiv AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("arXiv ML", "https://rss.arxiv.org/rss/cs.LG"),
    ("GitHub Blog AI/ML", "https://github.blog/ai-and-ml/feed/"),
]

AI_KEYWORDS = [
    "artificial intelligence", "ai ", " ai,", " ai.", "machine learning",
    "deep learning", "neural network", "large language model", "llm",
    "generative ai", "gen ai", "chatbot", "natural language processing",
    "computer vision", "reinforcement learning", "transformer model",
    "gpt", "chatgpt", "copilot", "midjourney", "stable diffusion",
    "diffusion model", "openai", "anthropic", "deepmind", "google ai",
    "meta ai", "nvidia", "hugging face", "huggingface", "mistral ai",
    "mistral", "cohere", "inflection", "perplexity", "claude", "gemini",
    "llama", "groq", "xai", "grok", "hacker news", "yc", "paper", "arxiv",
    "research repo", "open source model", "weights release", "benchmark",
]

TREND_TOPICS = {
    "OpenAI": ["openai", "chatgpt", "gpt-5", "gpt-4", "sora"],
    "Anthropic": ["anthropic", "claude", "mythos"],
    "Google / DeepMind": ["google", "deepmind", "gemini"],
    "Meta": ["meta", "llama", "zuckerberg"],
    "Nvidia / Chips": ["nvidia", "gpu", "chip", "chips", "semiconductor", "cuda"],
    "AI Agents": ["agent", "agents", "autonomous agent", "operator"],
    "Coding Tools": ["copilot", "cursor", "windsurf", "coding agent", "codegen"],
    "Robotics": ["robot", "robotics", "humanoid"],
    "Regulation / Policy": ["regulation", "policy", "lawsuit", "court", "senate", "judge", "eu ai act"],
    "Data Centers / Compute": ["data center", "datacenter", "compute", "inference", "training cluster"],
    "Funding / Deals": ["funding", "raised", "valuation", "acquisition", "ipo"],
    "Research / Papers": ["paper", "research", "benchmark", "arxiv", "study", "preprint"],
    "Open Source / Repos": ["github", "repo", "open source", "weights", "release", "model card"],
    "Builders / Creators": ["founder", "builder", "creator", "research lead", "engineer"],
}

SOURCE_TRUST_WEIGHTS = {
    "Reuters": 1.0,
    "MIT Technology Review": 0.98,
    "Wired": 0.96,
    "Ars Technica": 0.95,
    "The Verge": 0.93,
    "TechCrunch": 0.92,
    "VentureBeat": 0.91,
    "Fortune": 0.89,
    "GitHub Blog AI/ML": 0.62,
    "arXiv AI": 0.52,
    "arXiv ML": 0.52,
    "Hacker News": 0.72,
}

HN_SIGNAL_QUERIES = [
    "OpenAI", "Anthropic", "ChatGPT", "Claude", "Gemini", "LLM",
    "AI agent", "NVIDIA AI", "Mistral AI", "DeepMind",
]
