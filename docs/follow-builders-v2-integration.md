# Follow-Builders v2 Integration Room

## Why this exists
`follow-builders` is not just another feed. It brings:
- multiple content families (X, podcasts, blogs)
- source-specific prompts
- remote feed envelopes
- per-medium dedup state

If we jam that into the current daily digest as a random source list, the architecture turns into soup.

## Reserved Seams
### 1. Integration namespace
Use `ai_news_digest/integrations/follow_builders/`.
Current scaffold:
- `adapter.py`
- `MANIFEST`
- normalized remote feed adapter hook

### 2. Config namespace
Reserved env/config concepts:
- `FOLLOW_BUILDERS_ENABLED`
- `FOLLOW_BUILDERS_FEEDS_JSON`
- `FOLLOW_BUILDERS_PROMPT_STYLE`
- `FOLLOW_BUILDERS_SCHEMA_VERSION`

### 3. State namespace
Reserved state file:
- `data/state/follow_builders_state.json`

This is where remote feed versions, last seen items, and adapter metadata should live.

### 4. Prompt seams
v2 should support prompt routing by:
- integration
- content type
- stage

That means follow-builders can later bring prompts for:
- X summaries
- podcast summaries
- blog summaries
- digest intro assembly
- translation

### 5. Feed envelope expectations
Preferred normalized shape per remote feed item:
- `title`
- `summary`
- `url`
- `published`
- `source_type`
- `metadata`

## Recommended v2 path
1. ingest remote follow-builders feed envelopes first
2. normalize to digest article objects
3. keep builders content in its own section or profile
4. only later add deeper native adapter support

## What not to do
- do not hardcode follow-builders into `RSS_FEEDS`
- do not let builder-specific prompts leak into core news prompt logic
- do not share dedup keys across unrelated media without a namespace
