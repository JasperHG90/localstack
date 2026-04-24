---
name: daily-reflect
description: Produce a structured, retrievable daily reflection over the last 24h of Memex activity. Persistence is mandatory — the reflection note must exist every day, even when delivery is silent.
version: 1.0.0
metadata:
  hermes:
    tags: [knowledge, reflection, memex, daily]
    category: knowledge
---

## When to Use

Scheduled daily (midnight UTC). Also invoke manually when asked to produce "today's reflection" or "what did we learn yesterday."

## Configuration

- KV namespace: `app:hermes:reflection:*`
- Memex API: `$MEMEX_SERVER_URL/api/v1`, auth `-H "X-API-Key: $MEMEX_API_KEY"`
- Reflection author: `hermes-reflect` (distinct from plain `hermes` so reflections are filterable)

## Critical Rules

- **Persistence is mandatory.** Every run MUST produce a saved reflection note and a KV pointer, even when the day was thin. `[SILENT]` is a delivery decision, not a skip-the-work decision.
- **Use a deterministic title.** `Daily Reflection — YYYY-MM-DD` (UTC date of the run). Future sessions rely on this pattern for fallback search.
- **Use a deterministic note_key.** `hermes:reflection:YYYY-MM-DD`. Guarantees idempotency if the cron runs twice for the same day.
- **NEVER write post-mortem notes to Memex.** Report errors via a subagent with the `/post-mortem` skill.

## Procedure

### Phase 1: Load State

1. Compute today's UTC date as `YYYY-MM-DD` (call it `TODAY`) and the ISO timestamp 24h ago (call it `SINCE`).
2. Check the last reflection id for idempotency:
   ```bash
   curl -s -H "X-API-Key: $MEMEX_API_KEY" \
     "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:reflection:latest"
   ```
   If the latest reflection's note already has title `Daily Reflection — $TODAY`, skip to Phase 5 (self-check + deliver). Do not write a duplicate.

### Phase 2: Fetch Recent Notes

1. List notes created in the last 24h:
   ```bash
   curl -s -H "X-API-Key: $MEMEX_API_KEY" \
     "$MEMEX_SERVER_URL/api/v1/notes?sort=created_at:desc&limit=30&after=$SINCE"
   ```
2. For each note in the response collect: `id`, `title`, `author`, `tags`, `description`. That metadata is enough for reflection — do not fetch full bodies unless a description is missing and the title is ambiguous.
3. Exclude notes authored by `hermes-reflect` (do not reflect on your own output).

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

2. Base64-encode the body and create the note:
   ```bash
   CONTENT=$(printf '%s' "$BODY_MARKDOWN" | base64 -w0)
   curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
     "$MEMEX_SERVER_URL/api/v1/ingestions?background=true" \
     -d "{
       \"name\": \"Daily Reflection — $TODAY\",
       \"author\": \"hermes-reflect\",
       \"description\": \"Structured daily reflection over the 24h ending $TODAY UTC.\",
       \"tags\": [\"daily-reflection\", \"conclusion\", \"hermes-reflect\"],
       \"content\": \"$CONTENT\",
       \"vault_id\": \"global\",
       \"note_key\": \"hermes:reflection:$TODAY\"
     }"
   ```
   Capture the returned note `id` into `NOTE_ID`.

3. Write the KV pointer so future sessions can fetch today's reflection in one hop:
   ```bash
   curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
     "$MEMEX_SERVER_URL/api/v1/kv" \
     -d "{\"key\":\"app:hermes:reflection:latest\",\"value\":\"$NOTE_ID\"}"
   ```

4. Write the run timestamp:
   ```bash
   curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
     "$MEMEX_SERVER_URL/api/v1/kv" \
     -d "{\"key\":\"app:hermes:reflection:last_run\",\"value\":\"<ISO timestamp now>\"}"
   ```

If any of these three writes fails, DO NOT reply `[SILENT]`. Include the error in your Telegram reply and escalate via a subagent with the `/post-mortem` skill.

### Phase 5: Self-check

Confirm the new note is retrievable via semantic search — this is the exact failure mode we are guarding against:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/memories/search" \
  -d '{"query":"today daily reflection conclusions","limit":5}'
```

Find the rank of `$NOTE_ID` in the results (1-indexed). If it is not in the top 3, remember the rank and surface it in the reply.

### Phase 6: Deliver

Telegram reply, 4–6 lines:

- One line summary per section (Themes / Connections / Contradictions / Next actions).
- The note id: `note: $NOTE_ID`.
- If the self-check rank was > 3 or not found: append `⚠️ retrieval check failed (rank=N)` on its own line.

You may reply exactly `[SILENT]` ONLY when ALL of the following hold:
- Phase 4 steps 2, 3, 4 all succeeded.
- Every section in the note body is `_none observed_`.
- The self-check in Phase 5 found the note in the top 3.

Never combine `[SILENT]` with content.

## Error Handling

- Phase 2 list fails: abort the run, escalate via `/post-mortem`. Do not fabricate content.
- Phase 4 create fails: retry once after 5s. If still failing, abort and escalate.
- Phase 4 KV write fails: the note exists but the pointer doesn't — escalate via `/post-mortem` and still deliver the note id in the Telegram reply.
- Phase 5 search fails: treat as "retrieval check failed" and surface in the reply; do not abort.

## Pitfalls

- Do not reflect on `hermes-reflect`-authored notes — you will compound yesterday's conclusions into today's.
- Do not widen the tag list over time. The tag set `["daily-reflection","conclusion","hermes-reflect"]` is what sorting-hat and future retrievals key on.
- `note_key` must be `hermes:reflection:$TODAY` exactly — it is the idempotency guard for same-day reruns.
- Do not write the session transcript as the reflection. The reflection is a distilled artifact, not a dump of tool calls.
