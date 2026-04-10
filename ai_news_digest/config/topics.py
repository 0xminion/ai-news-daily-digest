from __future__ import annotations

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

HN_SIGNAL_QUERIES = [
    "OpenAI", "Anthropic", "ChatGPT", "Claude", "Gemini", "LLM",
    "AI agent", "NVIDIA AI", "Mistral AI", "DeepMind",
]
