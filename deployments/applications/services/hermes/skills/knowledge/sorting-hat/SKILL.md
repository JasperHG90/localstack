---
name: sorting-hat
description: Routes notes from the Memex inbox vault to appropriate destination vaults based on metadata
version: 1.0.0
metadata:
  hermes:
    tags: [knowledge, routing, memex, inbox]
    category: knowledge
---

## When to Use

Activate on a schedule to scan the `inbox` vault and route notes to their correct destination vaults. Every note that lands in inbox is a candidate for sorting.

## Procedure

### Phase 0: Discover Vaults

1. List all available vaults:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/vaults"
```

2. For each vault, note its name and description. These descriptions define what kind of content belongs in each vault.
3. The `inbox` vault is NEVER a valid destination -- it is the source you are sorting FROM.
4. If the only non-inbox vault is `global`, route everything there.

### Phase 1: Load State

1. Get the last run timestamp:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:sorting-hat:last_run"
```

If not found, this is the first run (use last 24 hours as the lookback window).

2. List already-routed note IDs:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv?key_prefix=app:hermes:sorting-hat:routed:"
```

Collect these into a set for filtering.

### Phase 2: Scan Inbox

1. Search for notes in the inbox vault. If `last_run` exists, use it as the `after` parameter. Otherwise, use the last 24 hours.

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/notes/search" \
  -d '{"query": "*", "vault_ids": ["inbox"], "after": "..."}'
```

2. Filter out any note IDs that appear in the routed set from Phase 1.
3. If no unprocessed notes remain, skip directly to Phase 4.

### Phase 3: Route Each Note

For each unprocessed note:

1. Get note metadata (title, tags, author, description) using the note ID from search results.

2. **Determine the target vault.** First, check the Routing Hints table below. If any rule matches, use that vault immediately. If no rule matches, use these fallback signals:
   - **Tags**: match tags against vault descriptions and purposes from Phase 0.
   - **Author**: certain authors map to certain vaults.
   - **Description**: use the content summary to judge the topic and match to vault purpose.
   - **Title**: use as a secondary signal when tags and description are ambiguous.

3. **If no vault clearly fits, route to `global`.** Do not leave notes unrouted. Do not create new vaults.

4. Migrate the note to the target vault:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/notes/{note_id}/migrate" \
  -d '{"target_vault_id": "target-vault-name"}'
```

5. Record the routing in KV (3-day TTL):

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:sorting-hat:routed:{note_id}", "value": "{target_vault}:{ISO-timestamp}", "ttl_seconds": 259200}'
```

### Phase 4: Update State

1. Write the current timestamp:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:sorting-hat:last_run", "value": "{ISO-timestamp}"}'
```

2. Write the count of notes routed this run:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:sorting-hat:last_count", "value": "{count}"}'
```

### Routing Hints

Check rules in order -- first match wins.

| Signal | Condition | Target Vault |
|--------|-----------|--------------|
| **Tags** | Any of: `trading`, `finance`, `market`, `briefing`, `session-log`, `trader-advisor`, `trend-scout`, `market-analyst` | `trading` |
| **Tags** | Any of: `SEC`, `sec-filing`, `10-K`, `10-Q`, `8-K`, `annual-report` | `SEC` |
| **Tags** | Any of: `cluster-watchdog`, `nomad`, `consul`, `infrastructure`, `triage`, `node-health` | `localstack` |
| **Tags** | Any of: `openfang`, `hermes`, `post-mortem`, `hand-error`, `system` | `openfang` |
| **Tags** | Any of: `memex`, `memex-plugin`, `vault`, `ingestion` | `memex` |
| **Tags** | Any of: `blog-scraper`, `medium-reader`, `engineering`, `agentic`, `ai`, `machine-learning` | `agentic` |
| **Author** | `trader-advisor` or `trend-scout` or `market-analyst` | `trading` |
| **Author** | `cluster-watchdog` | `localstack` |
| **Author** | `blog-scraper` or `medium-reader` | `agentic` |
| **Title** | Contains any of: `stock`, `price`, `market`, `trade`, `portfolio`, `DEGIRO`, `earnings`, `dividend` (case-insensitive) | `trading` |
| **Title** | Contains any of: `SEC`, `10-K`, `10-Q`, `filing`, `annual report` (case-insensitive) | `SEC` |
| **Title** | Contains any of: `cluster`, `node`, `Nomad`, `Consul`, `allocation`, `health report` (case-insensitive) | `localstack` |

If no rule matches, fall back to matching tags and description against vault descriptions from Phase 0. If that also produces no clear match, route to `global`.

### Routing Principles

- **Be decisive.** Every note must be routed somewhere. Prefer a reasonable guess over leaving a note in inbox.
- **Use vault descriptions as the primary guide.** The vault names and descriptions from Phase 0 define what belongs where.
- **Default to `global`.** When uncertain, `global` is the catch-all.
- **Never route to `inbox`.** That would create a loop.
- **One copy per note.** Do not route the same note to multiple vaults.

### Error Handling

- If vault listing fails: abort the run (you cannot route without knowing the vaults).
- If reading a specific note fails: skip it, log the error, continue with others.
- If note migration fails: skip that note, log the error, do NOT mark it as routed (it will be retried next run).
- Never fail the entire run because of one note.

When you encounter errors during routing (migration failures, vault errors, notes with missing metadata that cannot be routed), delegate to a subagent with the /post-mortem skill describing the issue. Include what went wrong, the root cause if identifiable, and a suggested fix. Do NOT report clean runs or "no notes to route."

## Pitfalls

- Never route a note back to `inbox` -- this creates an infinite loop.
- Always check the routed set before processing a note -- re-routing an already-routed note wastes work and can cause duplicates.
- KV namespace is `app:hermes:sorting-hat:` -- do not use the old `app:openfang:sorting-hat:` prefix.
- The TTL on routed keys is 3 days (259200 seconds). After that, the key expires and the note could be re-processed if it somehow ends up in inbox again.
