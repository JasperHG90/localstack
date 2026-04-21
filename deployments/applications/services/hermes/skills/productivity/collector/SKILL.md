---
name: collector
description: Autonomous intelligence monitor -- continuous web monitoring, change detection, knowledge graph updates, and event alerts
version: 1.0.0
metadata:
  hermes:
    tags: [productivity, intelligence, monitoring, alerts]
    category: productivity
---

## When to Use

Activate on a schedule to track targets (companies, sectors, instruments, people, technologies), collect data from the web, build knowledge over time, detect changes, and alert when something significant happens.

## Configuration

- **target_subject**: What to monitor (company, person, technology, market sector, etc.). Required.
- **collection_depth**: `surface` (headlines only), `deep` (full articles), or `exhaustive` (multi-hop research). Default: `deep`.
- **focus_area**: Intelligence lens to apply -- `market`, `business`, `competitor`, `technology`, or `general`. Default: `market`.
- **alert_on_changes**: Send a Telegram alert when significant changes are detected. Default: `true`.
- **max_sources_per_cycle**: How many sources to process each collection sweep (10, 30, 50, or 100). Default: `30`.
- **track_sentiment**: Analyse sentiment trends over time. Default: `true`.

## Procedure

### Memory

Use Memex for state and persistence (namespace: `app:hermes:collector:*`):

```bash
# Read state
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:collector:{key}"

# Write state
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:{key}", "value": "..."}'

# Search existing knowledge
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/notes/search" \
  -d '{"query": "..."}'

# Entity exploration
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/entities?q={topic}"
```

### Phase 0: Load State

1. Get last run timestamp:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:collector:last_run"
```

2. Get previous known state snapshot:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:collector:known_state"
```

3. Read `target_subject` and `focus_area` from configuration.

### Phase 1: Source Discovery

Based on `target_subject` and `focus_area`, construct search queries:

- **Market focus**: "{target} stock price", "{target} analyst rating", "{target} earnings"
- **Business focus**: "{target} partnerships", "{target} revenue", "{target} expansion"
- **Competitor focus**: "{target} vs {competitor}", "{target} market share"
- **Technology focus**: "{target} release", "{target} update", "{target} benchmark"

Run 5-15 `web_search` queries depending on `collection_depth`.

### Phase 2: Collection Sweep

For each search result:

1. Evaluate relevance (does it mention the target?).
2. Use `web_fetch` on promising URLs to extract: key facts, dates, names, numbers.
3. Tag data with confidence: HIGH (official source), MEDIUM (news), LOW (blog/social).
4. Compare against `known_state` from Phase 0 -- is this new information?

### Phase 3: Change Detection

Compare collected facts against the previous `known_state`:

- **New entity**: a person, company, product, or event not seen before
- **Changed attribute**: a number, status, or description that differs from last run
- **New relationship**: a connection between entities not previously known
- **Removed entity**: something in the previous state that is no longer mentioned

Score each change:

- **CRITICAL**: leadership change, acquisition, regulatory action, earnings surprise
- **IMPORTANT**: partnership, pricing change, product launch, analyst revision
- **MINOR**: blog mention, minor personnel change, routine update

### Phase 4: Persist and Alert

1. Update `known_state` in KV with the latest facts:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:known_state", "value": "{...updated facts...}"}'
```

2. Save a collection report to Memex:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/ingestions?background=true" \
  -d '{
    "name": "Collector Report: {target_subject} - {date}",
    "content": "<base64-encoded markdown>",
    "tags": ["collector", "intelligence", "{target_subject}"],
    "vault_id": "inbox",
    "description": "...",
    "author": "collector"
  }'
```

> **Note:** The `content` field must be base64-encoded: `echo -n "markdown content" | base64`
```

3. Update last run:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:last_run", "value": "{ISO-timestamp}"}'
```

4. If `alert_on_changes` is enabled AND any CRITICAL or IMPORTANT changes were detected, send via Telegram with the format:

> COLLECTOR -- {target}: {change_summary}

If no significant changes, do nothing (no Telegram spam on quiet days).

### Phase 5: Stats

Update KV counters:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:data_points", "value": "{total}"}'

curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:entities_tracked", "value": "{count}"}'

curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:reports_generated", "value": "{count}"}'

curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:collector:last_update", "value": "{ISO-timestamp}"}'
```

### Guidelines

- Attribute every fact to its source
- Distinguish facts from analysis
- Respect rate limits -- do not hammer the same domain
- Prioritise recent information over old
- If the target is not found in search results, say so -- do not fabricate data

## Pitfalls

- Always load the previous `known_state` before collection so change detection works correctly. Without it, every fact looks new.
- Only send Telegram alerts for CRITICAL or IMPORTANT changes -- never for MINOR changes or quiet runs.
- KV namespace is `app:hermes:collector:` -- do not use the old `app:openfang:collector:` prefix.
- Respect web rate limits. Do not fetch the same domain more than a few times per cycle.
