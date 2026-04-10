from __future__ import annotations

import re

# Structured keyword groups for robust AI/ML matching.
# Each group is a tuple of (compiled_regex, description).
# Regex-based matching avoids brittle substring hacks like " ai " with spaces.

_AI_PATTERNS = [
    # Explicit AI/ML terms (word-boundary matched)
    (re.compile(r'\b(?:artificial intelligence|machine learning|deep learning)\b', re.I), 'core-ai'),
    (re.compile(r'\b(?:neural net(?:work)?s?|transformer(?:\s+model)?s?)\b', re.I), 'model-arch'),
    (re.compile(r'\b(?:large language model|llm[s]?|foundation model)\b', re.I), 'llm'),
    (re.compile(r'\b(?:generative\s+ai|gen\s+ai)\b', re.I), 'genai'),
    (re.compile(r'\b(?:natural language processing|nlp|computer vision|reinforcement learning)\b', re.I), 'ai-subfield'),
    (re.compile(r'\b(?:diffusion model|stable diffusion|midjourney)\b', re.I), 'image-gen'),
    (re.compile(r'\bchatbot\b', re.I), 'chatbot'),
    (re.compile(r'\bbenchmark\b', re.I), 'benchmark'),

    # Standalone "AI" as a word (not part of other words like "maintain", "certain")
    # Matches "AI" when surrounded by non-alpha chars or at string boundaries
    # Also matches "A.I." with dots
    (re.compile(r'(?<![a-zA-Z])a\.?i\.?(?![a-zA-Z])', re.I), 'standalone-ai'),

    # Company/product names strongly associated with AI
    (re.compile(r'\b(?:openai|chatgpt|gpt-[345]|sora)\b', re.I), 'openai'),
    (re.compile(r'\b(?:anthropic|claude|mythos)\b', re.I), 'anthropic'),
    (re.compile(r'\b(?:deepmind|gemini)\b', re.I), 'google-ai'),
    (re.compile(r'\b(?:hugging\s?face|huggingface)\b', re.I), 'huggingface'),
    (re.compile(r'\b(?:mistral|cohere|perplexity)\b', re.I), 'ai-startup'),
    (re.compile(r'\b(?:groq|xai)\b', re.I), 'ai-infra'),
    (re.compile(r'\bgrok\b(?=\s+(?:model|ai|llm|api))', re.I), 'ai-infra'),
    (re.compile(r'\b(?:llama|meta\s+ai)\b', re.I), 'meta-ai'),
    (re.compile(r'\bnvidia\b.*\b(?:ai|gpu|cuda|chip)\b', re.I), 'nvidia-ai'),

    # AI coding tools
    (re.compile(r'\b(?:copilot|cursor|windsurf|codegen)\b', re.I), 'ai-coding'),

    # Research signals
    (re.compile(r'\barxiv\b', re.I), 'arxiv'),
    (re.compile(r'\b(?:open[\s-]?source\s+model|weights?\s+release)\b', re.I), 'oss-model'),
]

def matches_ai_keywords(text: str) -> bool:
    """Check if text matches any AI/ML keyword pattern.

    Uses regex with word boundaries instead of brittle substring matching.
    Returns True if any pattern matches.
    """
    return any(pattern.search(text) for pattern, _ in _AI_PATTERNS)


def get_matched_tags(text: str) -> list[str]:
    """Return list of matched keyword tags for debugging/ranking."""
    return [tag for pattern, tag in _AI_PATTERNS if pattern.search(text)]
