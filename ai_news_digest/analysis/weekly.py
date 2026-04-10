from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ai_news_digest.analysis.clustering import cluster_articles
from ai_news_digest.analysis.trends import extract_topics
from ai_news_digest.config import (
    WEEKLY_DIRECTIONS_COUNT,
    WEEKLY_EMERGING_COUNT,
    WEEKLY_FOCUS_COUNT,
    WEEKLY_HIGHLIGHTS_COUNT,
    WEEKLY_QUESTIONS_COUNT,
    WEEKLY_RESEARCH_SIGNALS_COUNT,
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


def _signal_subtype(item: dict) -> str:
    source = (item.get('source') or '').lower()
    url = (item.get('url') or '').lower()
    headline = (item.get('headline') or item.get('title') or '').lower()
    if 'arxiv' in source:
        return 'paper'
    if 'github' in source or 'repo' in headline or 'repository' in headline:
        return 'repo'
    if 'follow builders' in source:
        return 'builder feed'
    if any(token in url for token in ('docs.', '/docs', 'documentation')) or 'docs' in headline:
        return 'product doc'
    return 'product / launch'


def _confidence_from_score(score: float, cluster_size: int = 1) -> str:
    if score >= 5 or cluster_size >= 4:
        return 'High confidence'
    if score >= 3 or cluster_size >= 2:
        return 'Medium confidence'
    return 'Early signal'


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
                'confidence': _confidence_from_score(score, len(cluster['articles'])),
                'subtype': _signal_subtype(rep),
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
            'confidence': _confidence_from_score(mean(scores), len(scores)),
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
                'confidence': item['confidence'],
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

    missed_but_emerging = []
    for item in main_summaries[WEEKLY_HIGHLIGHTS_COUNT: WEEKLY_HIGHLIGHTS_COUNT + max(3, WEEKLY_EMERGING_COUNT * 2)]:
        if item['cluster_size'] <= 2:
            missed_but_emerging.append(
                {
                    'headline': item['headline'],
                    'source': item['source'],
                    'url': item['url'],
                    'subtype': item['subtype'],
                    'confidence': 'Early signal',
                    'why_now': 'It is not dominant yet, but it showed enough repeat signal that it may matter next week.',
                    'eli5': 'ELI5: This is a smaller story that might turn into a bigger one soon.',
                }
            )
        if len(missed_but_emerging) >= WEEKLY_EMERGING_COUNT:
            break

    return {
        'window_days': days,
        'executive_summary': executive_summary,
        'highlights_of_the_week': main_summaries[:WEEKLY_HIGHLIGHTS_COUNT],
        'trending_directions': directions[:WEEKLY_DIRECTIONS_COUNT],
        'research_focus': focus,
        'thinking_prompts': prompts[:WEEKLY_QUESTIONS_COUNT],
        'research_builder_signals': research_summaries[:WEEKLY_RESEARCH_SIGNALS_COUNT],
        'missed_but_emerging': missed_but_emerging,
    }


def build_weekly_preview(payload: dict) -> str:
    lines = ['WEEKLY PREVIEW:']
    for item in payload.get('highlights_of_the_week', [])[:2]:
        lines.append(f"- Highlight: {item['headline']}")
    for item in payload.get('trending_directions', [])[:2]:
        lines.append(f"- Direction: {item['topic']} — {item['direction']} ({item.get('confidence', 'n/a')})")
    if payload.get('research_focus'):
        focus = payload['research_focus'][0]
        lines.append(f"- Focus: {focus['topic']} — {focus['why_now']} ({focus.get('confidence', 'n/a')})")
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
        lines.append(f"   Confidence: {item.get('confidence', 'n/a')}")
        lines.append(f"   {item['why_it_matters']}")
        lines.append(f"   {item['eli5']}")
        lines.append(f"   Source: {item['source']} - {item['url']}")
    lines.extend(['', 'Trending and Directions:'])
    for item in payload.get('trending_directions', []):
        lines.append(f"- {item['topic']} — {item['direction']} [{item.get('confidence', 'n/a')}] ({item['note']})")
    lines.extend(['', 'Areas of Focus to Research:'])
    for item in payload.get('research_focus', []):
        lines.append(f"- {item['topic']} [{item.get('confidence', 'n/a')}]: {item['why_now']}")
        lines.append(f"  Watch: {item['what_to_watch']}")
    if payload.get('research_builder_signals'):
        lines.extend(['', 'Research / Builder Signals:'])
        for item in payload['research_builder_signals']:
            lines.append(f"- [{item.get('subtype', 'signal')}] {item['headline']} ({item['source']})")
            lines.append(f"  Confidence: {item.get('confidence', 'n/a')}")
            lines.append(f"  {item['eli5']}")
    if payload.get('missed_but_emerging'):
        lines.extend(['', 'Missed but Emerging:'])
        for item in payload['missed_but_emerging']:
            lines.append(f"- [{item.get('subtype', 'signal')}] {item['headline']} ({item['source']})")
            lines.append(f"  Confidence: {item.get('confidence', 'n/a')}")
            lines.append(f"  {item['eli5']}")
    lines.extend(['', 'Question Prompts:'])
    for q in payload.get('thinking_prompts', []):
        lines.append(f"- {q}")
    return '\n'.join(lines)
