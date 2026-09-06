---
name: daily-reflect
description: Produce a structured, retrievable daily reflection over the last 24h of OpenViking activity. Persistence is mandatory — the reflection note must exist every day, even when delivery is silent.
version: 1.1.0
metadata:
  hermes:
    tags: [knowledge, reflection, openviking, daily]
    category: knowledge
---

## When to Use

Scheduled daily (midnight UTC). Also invoke manually when asked to produce "today's reflection" or "what did we learn yesterday."

## Configuration

- Use the native OpenViking tools (`viking_*`). Do not shell out to curl.
- Idempotency ("did I already reflect today?") needs an EXACT-KEY read, which
  OpenViking cannot do -- it is a semantic store. Keep it in
  `$HERMES_HOME/state/daily-reflect.json` via the `files` toolset.
- Open every reflection body with the line `Daily Reflection — $TODAY
  (hermes-reflect)`, so it is recognisable in search results and you can tell
  your own output apart from what you are reflecting on.

## Critical Rules

- **Persistence is mandatory.** Every run MUST produce a stored reflection and a state write, even when the day was thin. `[SILENT]` is a delivery decision, not a skip-the-work decision.
- **Use a deterministic title.** `Daily Reflection — YYYY-MM-DD` (UTC date of the run). Future sessions rely on this pattern for fallback search.
- **Use a deterministic note_key.** `hermes:reflection:YYYY-MM-DD`. Guarantees idempotency if the cron runs twice for the same day.
- **NEVER write post-mortem notes to OpenViking.** Report errors via a subagent with the `/post-mortem` skill.

## Procedure

### Phase 1: Load State

1. Compute today's UTC date as `YYYY-MM-DD` (call it `TODAY`) and the ISO timestamp 24h ago (call it `SINCE`).
2. Read `$HERMES_HOME/state/daily-reflect.json`. If `latest_date` equals
   `$TODAY`, a reflection already exists: skip to Phase 5. Do not write a
   duplicate. A missing file is a first run.

### Phase 2: Fetch Recent Notes

1. `viking_browse(action="list", path="viking://user/jasper/memories")` for
   what has been stored, and `viking_search(query="<the day's themes>",
   mode="deep", limit=30)` for anything the browse misses.

   There is no `since` filter and no ingest-time sort: OpenViking ranks by
   meaning, not recency. Judge each hit's date from its own content and drop
   what is older than `$SINCE`.
2. Read each candidate at `level="abstract"` first. Go to `level="overview"`
   only when the abstract is too thin to place the item, and to `"full"`
   almost never.
3. Skip anything whose first line marks it as a previous daily reflection --
   do not reflect on your own output.

### Phase 3: Reflect

Read across the fetched notes and identify:

- **Themes** — topics that show up more than once, or that thread across otherwise-unrelated notes.
- **Connections** — pairs/triples of notes from different vaults or authors that speak to the same underlying thing.
- **Contradictions & open questions** — claims that conflict, or questions raised in the notes that were not resolved.
- **Next actions** — concrete follow-ups implied by the day's notes (a fix to land, a question to answer, a decision to make).

If a section has genuinely nothing, write `_none observed_` for that section. Do not fabricate.

### Phase 4: Persist (MANDATORY)

1. Build the note body as clean markdown with four H2 sections in this exact order:
   - `## Themes`
   - `## Connections`
   - `## Contradictions & open questions`
   - `## Next actions`

   Keep each section short — bullet list preferred, no section over ~150 tokens.

2. Store the reflection:
   ```
   viking_remember(
     content=$BODY_MARKDOWN,   # first line: Daily Reflection — $TODAY (hermes-reflect)
     category="event"
   )
   ```
   `category="event"` because a reflection is a thing that happened on a date.
   There is no note key and no upsert -- Phase 1's state read is the only
   thing stopping a duplicate.

3. Record that today is done, so Phase 1 can short-circuit tomorrow:
   ```
   $HERMES_HOME/state/daily-reflect.json
     latest_date = "$TODAY"
     last_run    = "<ISO timestamp now>"
   ```
   Read-modify-write the whole file.

If either of these writes fails, DO NOT reply `[SILENT]`. Include the error in your Telegram reply and escalate via a subagent with the `/post-mortem` skill.

### Phase 5: Self-check

Confirm the reflection is retrievable — this is the exact failure mode we are
guarding against, and it matters more here than it did with note ids, because
semantic search is now the only way back to it:

```
viking_search(query="daily reflection $TODAY themes and next actions", limit=5)
```

Find the rank of today's reflection (1-indexed) by its first line. If it is
not in the top 3, surface the rank in the reply: a reflection that cannot be
found again is a reflection that was not really saved.

### Phase 6: Deliver

Telegram reply, 4–6 lines:

- One line summary per section (Themes / Connections / Contradictions / Next actions).
- The self-check rank: `retrievable at rank N`.
- If the self-check rank was > 3 or not found: append `⚠️ retrieval check failed (rank=N)` on its own line.

You may reply exactly `[SILENT]` ONLY when ALL of the following hold:
- Phase 4 steps 2 and 3 both succeeded.
- Every section in the note body is `_none observed_`.
- The self-check in Phase 5 found the note in the top 3.

Never combine `[SILENT]` with content.

## Error Handling

- Phase 2 fetch fails: abort the run, escalate via `/post-mortem`. Do not fabricate content.
- Phase 4 `viking_remember` fails: retry once after 5s. If still failing, abort and escalate.
- Phase 4 state write fails: the reflection exists but tomorrow will not know it — escalate via `/post-mortem` and say so in the Telegram reply, because the next run will write a duplicate.
- Phase 5 `viking_search` fails: treat as "retrieval check failed" and surface in the reply; do not abort.

## Pitfalls

- Do not reflect on `hermes-reflect`-authored notes — you will compound yesterday's conclusions into today's.
- Do not widen the tag list over time. The tag set `["daily-reflection","conclusion","hermes-reflect"]` is what sorting-hat and future retrievals key on.
- `note_key` must be `hermes:reflection:$TODAY` exactly — it is the idempotency guard for same-day reruns.
- Do not write the session transcript as the reflection. The reflection is a distilled artifact, not a dump of tool calls.
