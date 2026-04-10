from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ai_news_digest.analysis.clustering import cluster_articles
from ai_news_digest.analysis.trends import extract_topics
from ai_news_digest.config import (
    WEEKLY_DIRECTIONS_COUNT,
    WEEKLY_FOCUS_COUNT,
    WEEKLY_HIGHLIGHTS_COUNT,
    WEEKLY_QUESTIONS_COUNT,
)
from ai_news_digest.storage.archive import load_recent_report_payloads

RESEARCH_SOURCES = {
    'arXiv AI',
    'arXiv ML',
    'GitHub Blog AI/ML',
    'Follow Builders / x',
    'Follow Builders / podcasts',
    'Follow Builders / blogs',
}


def _summarize_clusters(clusters: list[dict]) -> list[dict]:
    cluster_summaries = []
    for cluster in clusters:
        rep = cluster['representative']
        topics = set()
        for article in cluster['articles']:
            topics.update(extract_topics(article))
        score = len(cluster['articles']) + rep.get('source_count', 1) + (rep.get('hn_points', 0) / 100)
        cluster_summaries.append(
            {
                'headline': rep.get('title'),
                'source': rep.get('source'),
                'url': rep.get('url'),
                'cluster_size': len(cluster['articles']),
                'source_count': rep.get('source_count', 1),
                'topics': sorted(topics),
                'score': round(score, 2),
                'why_it_matters': f"Seen across {len(cluster['articles'])} article(s) from {rep.get('source_count', 1)} source(s).",
                'eli5': 'ELI5: This kept showing up enough times that it probably mattered more than one random headline.',
            }
        )
    cluster_summaries.sort(key=lambda item: (item['score'], item['cluster_size'], item['source_count']), reverse=True)
    return cluster_summaries


def build_weekly_highlights_payload(days: int = 7) -> dict:
    payloads = load_recent_report_payloads(days=days, include_today=True)
    main_articles = []
    research_articles = []
    topic_counts = defaultdict(list)

    for payload in payloads:
        for article in payload.get('articles', []):
            if article.get('source') in RESEARCH_SOURCES:
                research_articles.append(article)
            else:
                main_articles.append(article)

    main_clusters = cluster_articles(main_articles)
    research_clusters = cluster_articles(research_articles)
    main_summaries = _summarize_clusters(main_clusters)
    research_summaries = _summarize_clusters(research_clusters)

    for item in main_summaries:
        for topic in item['topics']:
            topic_counts[topic].append(item['score'])

    directions = [
        {
            'topic': topic,
            'direction': 'rising' if mean(scores) >= 2 else 'steady',
            'evidence_score': round(mean(scores), 2),
            'note': f"Supported by {len(scores)} cluster(s) this week.",
        }
        for topic, scores in topic_counts.items()
    ]
    directions.sort(key=lambda item: item['evidence_score'], reverse=True)

    focus = []
    for item in directions[:WEEKLY_FOCUS_COUNT]:
        focus.append(
            {
                'topic': item['topic'],
                'why_now': f"{item['topic']} kept showing up with evidence score {item['evidence_score']}.",
                'what_to_watch': 'Watch for stronger source breadth, repeated mentions, and concrete launches/deployments.',
            }
        )

    prompt_templates = [
        'What changes if {topic} keeps accelerating for another month?',
        'What would falsify the current read on {topic}?',
        'Which companies or builders benefit most if {topic} becomes the dominant direction?',
        'What bottleneck is actually being solved inside {topic}?',
        'Where is hype outrunning evidence in {topic}?',
        'What should be monitored daily to catch the next turn in {topic}?',
    ]
    prompts = [
        prompt_templates[idx % len(prompt_templates)].format(topic=item['topic'])
        for idx, item in enumerate(directions[: max(1, WEEKLY_QUESTIONS_COUNT)])
    ]

    executive_summary = 'This week was mostly about which AI stories stayed alive long enough to matter, which directions kept building momentum, and which research or builder signals looked early but worth watching.'

    return {
        'window_days': days,
        'executive_summary': executive_summary,
        'highlights_of_the_week': main_summaries[:WEEKLY_HIGHLIGHTS_COUNT],
        'trending_directions': directions[:WEEKLY_DIRECTIONS_COUNT],
        'research_focus': focus,
        'thinking_prompts': prompts[:WEEKLY_QUESTIONS_COUNT],
        'research_builder_signals': research_summaries[:4],
    }


def build_weekly_preview(payload: dict) -> str:
    lines = ['WEEKLY PREVIEW:']
    for item in payload.get('highlights_of_the_week', [])[:2]:
        lines.append(f"- Highlight: {item['headline']}")
    for item in payload.get('trending_directions', [])[:2]:
        lines.append(f"- Direction: {item['topic']} — {item['direction']}")
    if payload.get('research_focus'):
        lines.append(f"- Focus: {payload['research_focus'][0]['topic']} — {payload['research_focus'][0]['why_now']}")
    if payload.get('thinking_prompts'):
        lines.append(f"- Question: {payload['thinking_prompts'][0]}")
    return '\n'.join(lines)


def render_weekly_highlights(payload: dict) -> str:
    lines = ['AI Weekly Highlights', '']
    if payload.get('executive_summary'):
        lines.extend(['Executive Summary:', payload['executive_summary'], ''])
    lines.append('Highlights of the Week:')
    for idx, item in enumerate(payload.get('highlights_of_the_week', []), start=1):
        lines.append(f"{idx}. {item['headline']}")
        lines.append(f"   {item['why_it_matters']}")
        lines.append(f"   {item['eli5']}")
        lines.append(f"   Source: {item['source']} - {item['url']}")
    lines.extend(['', 'Trending and Directions:'])
    for item in payload.get('trending_directions', []):
        lines.append(f"- {item['topic']} — {item['direction']} ({item['note']})")
    lines.extend(['', 'Areas of Focus to Research:'])
    for item in payload.get('research_focus', []):
        lines.append(f"- {item['topic']}: {item['why_now']}")
        lines.append(f"  Watch: {item['what_to_watch']}")
    if payload.get('research_builder_signals'):
        lines.extend(['', 'Research / Builder Signals:'])
        for item in payload['research_builder_signals']:
            lines.append(f"- {item['headline']} ({item['source']})")
            lines.append(f"  {item['eli5']}")
    lines.extend(['', 'Question Prompts:'])
    for q in payload.get('thinking_prompts', []):
        lines.append(f"- {q}")
    return '\n'.join(lines)
