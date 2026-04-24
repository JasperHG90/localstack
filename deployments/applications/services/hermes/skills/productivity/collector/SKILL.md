---
name: collector
description: Autonomous intelligence monitor -- continuous web monitoring, change detection, knowledge graph updates, and event alerts
version: 1.1.0
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
- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl.

## Procedure

### Memory

Use Memex for state and persistence (namespace: `app:hermes:collector:*`):

```
memex_kv_get(key="app:hermes:collector:{key}")
memex_kv_write(key="app:hermes:collector:{key}", value="...")
memex_retrieve_notes(query="...")   # search existing knowledge
memex_list_entities(query="{topic}") # entity exploration
```

### Phase 0: Load State

1. Get last run timestamp:

```
memex_kv_get(key="app:hermes:collector:last_run")
```

2. Get previous known state snapshot:

```
memex_kv_get(key="app:hermes:collector:known_state")
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

```
memex_kv_write(key="app:hermes:collector:known_state", value="{...updated facts...}")
```

2. Save a collection report to Memex:

```
memex_retain(
  title="Collector Report: {target_subject} - {date}",
  author="collector",
  description="...",
  tags=["collector", "intelligence", "{target_subject}"],
  markdown_content=$REPORT_MARKDOWN,
  vault_id="inbox",
  background=True
)
```

Capture the returned note id into `NOTE_ID` if you need it later.

3. Update last run:

```
memex_kv_write(key="app:hermes:collector:last_run", value="{ISO-timestamp}")
```

4. If `alert_on_changes` is enabled AND any CRITICAL or IMPORTANT changes were detected, send via Telegram with the format:

> COLLECTOR -- {target}: {change_summary}

If no significant changes, do nothing (no Telegram spam on quiet days).

### Phase 5: Stats

Update KV counters:

```
memex_kv_write(key="app:hermes:collector:data_points", value="{total}")
memex_kv_write(key="app:hermes:collector:entities_tracked", value="{count}")
memex_kv_write(key="app:hermes:collector:reports_generated", value="{count}")
memex_kv_write(key="app:hermes:collector:last_update", value="{ISO-timestamp}")
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
