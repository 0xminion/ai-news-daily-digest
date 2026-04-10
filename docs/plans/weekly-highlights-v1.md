# Weekly Highlights v1 Design

> Goal: turn 7 daily digests into one useful weekly synthesis instead of a bloated scrapbook.

## Objectives
- Surface the most important AI developments of the week.
- Show which directions are heating up, fading, or stabilizing.
- Identify 1-3 areas worth deeper follow-up research next week.
- End with prompts that force thinking instead of repeating obvious headlines.

## Inputs
- Last 7 archived daily digest payloads from `data/daily_reports/*/digest.json`
- Cluster metadata (`clusters`)
- Trend metadata (`trends`)
- Ranked articles with signal annotations (HN, source_count, ranking_score)
- Topic memory snapshots from `data/state/topic_memory.json`

## Pipeline
1. Load archived daily payloads for the last 7 days.
2. Flatten all archived articles into a weekly pool.
3. Re-cluster weekly items into canonical story threads.
4. Score weekly threads using:
   - persistence across days
   - source breadth
   - daily ranking scores
   - HN technical attention
   - topic momentum
5. Build four sections:
   - Highlights of the Week
   - Trending and Directions
   - Areas of Focus to Research
   - Question Prompts
6. Save weekly text + JSON artifact under `data/weekly_reports/YYYY-Www/`.

## Suggested Scoring
`weekly_score = 0.30 * persistence + 0.20 * source_breadth + 0.20 * avg_daily_score + 0.15 * technical_attention + 0.15 * momentum`

## Output Shape
- Executive Summary (4-6 sentences)
- Highlights of the Week (5-7)
- Trending and Directions (3-5)
- Areas of Focus to Research (2)
- Question Prompts (5-8)

## Section Rules
### Highlights of the Week
Each highlight should include:
- headline
- why it mattered
- how many days it stayed alive
- how many sources covered it

### Trending and Directions
Each direction should answer:
- what is moving
- why it is moving
- whether it looks accelerating, steady, or fading

### Areas of Focus to Research
Each area should include:
- why now
- what signal would confirm it
- what would weaken the thesis

### Question Prompts
Prompt categories:
- implication
- uncertainty
- technical bottleneck
- market structure
- policy / governance

## Implementation Notes
- Weekly output should be generated without refetching the web.
- It should depend on archived daily payloads only.
- This keeps cost low and makes weekly results reproducible.

## Future Upgrades
- compare this week vs prior week
- builder-specific weekly section from follow-builders integration
- cluster-level sentiment drift
- recurring-theme watchlist
