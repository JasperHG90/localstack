## Critical constraints

<critical_constraint name="record_outcome_shape">
`memex_record_outcome` requires `units=[{unit_id, verb, reason}]`. Bare `success=True` → HTTP 400.
</critical_constraint>

<critical_constraint name="observation_read_only">
Observations (`unit_metadata.virtual: true`) are read-only projections of MUs; `memex_memory_deprioritize` on an observation UUID returns HTTP 400 with `source_memory_units`. Re-issue against one of the listed MU IDs.
</critical_constraint>

<critical_constraint name="kv_scope_qualifier">
KV namespace = scope qualifier (NOT grammatical person). "I prefer X for this project" → `project:<id>:` not `user:`.
</critical_constraint>

<critical_constraint name="citations_required">
Cite every load-bearing claim grounded in Memex content. Never fabricate titles/ids.
</critical_constraint>

## Storage layers

- **Notes** — markdown source. `memex_add_note` for first capture; `memex_append_note(note_key, delta)` to extend (never re-ingest whole body).
- **Memory units** — append-only facts extracted from notes. NEVER edit/replace/delete. To record a change, ingest a new note; contradiction detection runs at extraction.
- **KV store** — namespaced operational state. Mutable upsert by key.

Reflection produces per-entity mental models (read-only — surface via `memex_memory_search` / `memex_survey`).

## Retrieval routing

Match the query shape; call the listed tool(s):

- **Title fragment** → `memex_find_note` → `memex_get_page_indices` + `memex_get_nodes`.
- **Relationships** → `memex_list_entities` → `memex_get_entity_cooccurrences` → `memex_get_entity_mentions`.
- **Specific fact / single question** → `memex_memory_search` AND `memex_note_search` in parallel. Retry `expand_query=true` if insufficient.
- **Comprehensive view of a topic/entity** ("everything/overview/tell me all about X") → `memex_survey(query)` FIRST, OR ≥3 facet-scoped `memex_memory_search` calls. One search result is NEVER enough. <example>"Tell me everything about Topic-X" → WRONG: one `memex_memory_search("Topic-X")`. RIGHT: `memex_survey("Topic-X")`, or 3 facet-scoped `memex_memory_search` → consolidate.</example>
- **Broad/panoramic** (vault-wide, no topic) → `memex_get_vault_summary` first; escalate to `memex_survey(query)` if too coarse.
- **KV** ("what's our X?" / "what convention?" / "what do I prefer?" / "what setting?") → `memex_kv_get(key)` / `memex_kv_search(query)` / `memex_kv_list()`. Preferences/conventions/settings live in KV, not on disk — answer from `memex_kv_get`/`memex_kv_search` before inspecting local files (`ls`/`Glob`/`Read`/`Bash`). Wake words route verbatim: `KV: get <key>`, `KV: search <query>`, `Store in KV: <key>=<value>`. (How-to procedures are NOT KV → procedural plane.)

After `memory_search`: call `memex_get_notes_metadata`. After `note_search`: metadata is inline — do NOT call `memex_get_notes_metadata`. `memex_read_note` only when `total_tokens < 500`.

For list-shape browse tools (`memex_recent_notes`, `memex_list_notes`, `memex_list_entities`), pass `slim=True` when you need only IDs/titles/timestamps — drops summaries + descriptions to fit tool-output caps. Default `slim=False`.

## Search query formulation

Formulate search queries as natural language, not as keyword lists (NEVER as keyword lists). Preserve proper nouns, amounts, dates, and qualifiers from the original question, and search for the subject/activity rather than the answer type.

<example>"When did we last rotate the prod DB credentials?" → WRONG: `memex_memory_search("prod DB credentials rotation date")` (keywords + answer-type). RIGHT: `memex_memory_search("When did we last rotate the prod database credentials?")`.</example>

## 5-step resolution flow

<critical_constraint name="outcome_routing">
Triggers: success — "that worked", "that fixed it", "yes, that did it", "perfect", "record it as a success", "save this approach"; failure — "stop suggesting X", "didn't work", "we removed it", "that was wrong", "drop that idea". These ALWAYS route to `memex_record_outcome` on EXISTING units; NEVER to `memex_add_note`. The outcome is a counter increment on the unit's Memory Worth — a new note describing the success is NOT detected as an outcome.
</critical_constraint>

<example>"That fixed it, record it as a success." → WRONG: `memex_add_note(title="Resolution: X worked")`. RIGHT: `memex_memory_search` for candidate units → READ bodies → `memex_record_outcome(units=[{unit_id, verb:"helpful", reason}])`.</example>

1. **Disambiguate** — ambiguous scope (multiple candidates, no temporal anchor)? ASK before writing.
2. **Route** — title → `memex_find_note`; content → `memex_memory_search`. Pick one:
   - A entity-anchored: `memex_list_entities` → `memex_get_entity_mentions`.
   - B cross-note: `memex_memory_search(limit=30)`. `limit` must be ≥30 (limit=30 — outcome judging needs a wide candidate pool; the default 10 misses the unit you're stamping).
   - C single-note: `memex_get_page_indices` → `memex_get_memory_units(chunk_ids=…)`.
3. **Judge** — READ unit bodies; pick outcome-relevant subset. NEVER bulk-write.
4. **+5. Paired writes** on the judged subset:
   - Success → `memex_record_outcome(units=[{unit_id, verb:"helpful", reason}])`. No deprio.
   - Failure → `memex_record_outcome(units=[{unit_id, verb:"not_helpful", reason}])` AND `memex_memory_deprioritize(unit_id, reason)`. SAME subset.

## Orthogonal axes

- `memex_record_outcome` = MW gradient (append-only; not reversible).
- `memex_memory_deprioritize` = binary surface state (reversible via `memex_memory_restore`).

User-confirmed-fix stamps BOTH.

## Historical / audit routing

Triggers: "evolved", "used to", "history of", "what changed", "audit".

- Specific unit → `memex_get_unit_history(unit_id)`.
- Broad audit → `memex_memory_search(apply_pre_filter=False)` (bypasses MW/FSFM/confidence filters).

## Read-only observations

<critical_constraint name="virtual_unit_filter">
Mental-model observations are read-only projections of memory units (`unit_metadata.virtual: true`). `memex_memory_deprioritize` on an observation UUID returns HTTP 400 with `{source_memory_units: [...]}`; re-issue against one of those MU IDs to suppress the underlying fact. Observations refresh asynchronously on the surviving evidence.

An observation's `evidence` may include STALE memory units (superseded by a newer contradicting note). STALE evidence stays cited as historical support and is NOT auto-pruned — treat it as audit-trail, not an active claim.
</critical_constraint>

## Preferences / conventions → `memex_kv_put`, NOT local files

<critical_constraint name="kv_routing">
"remember"/"save"/"for future sessions"/"going forward" directives conveying a preference, convention, or setting → `memex_kv_put`. Do NOT write to local files (CLAUDE.md, AGENTS.md, .memex/), do NOT use `memex_add_note`, do NOT just acknowledge.
</critical_constraint>

Pick the namespace by scope cue (NOT grammatical person). `app:`/`project:`/`global:` ALL override `user:` when their cue is present; default `user:` only when NO other cue applies.

| Scope cue | Namespace |
|---|---|
| identity ("about me", "I prefer X") | `user:` |
| "this repo/project", "in this codebase" | `project:<id>:` |
| "company-wide", "we standardise on" | `global:` |
| "when I use <app>", "in Claude Code/Hermes" | `app:<app-id>:` |

<critical_constraint name="kv_vs_procedural">
KV holds ONE static binding — a PREFERENCE / SETTING / CONVENTION ("Python 3.12", "dark theme", "lint before commit"). A multi-step WORKFLOW you'd reuse and search ("how we deploy", "release steps") is NOT KV → procedural plane (`memex_procedural_search` to recall, `memex_case_submit` to write). No KV `procedure:` namespace — the plane is its only home.
</critical_constraint>

Ambiguous? ASK before writing.

<example>"I prefer Neovim" → `user:editor`</example>
<example>"For this project: Python 3.10" → `project:<id>:lang:python`</example>
<example>"Company-wide: Python 3.12 min" → `global:lang:python:min`</example>
<example>"When I use Claude Code: dark theme" → `app:claude-code:theme` (<app> cue beats "I"/"my")</example>
<example>"Always lint before commit" → `global:lint:commit` (one-line convention, not a workflow)</example>
<example>"How we deploy: check status, verify secrets, push, health-check" → procedural plane, NOT KV</example>

## Citations

Cite source notes inline for every claim grounded in Memex content: `…claim [note-title-or-id].`

One reference per load-bearing claim. Never fabricate titles or ids — say "I cannot identify a specific source" instead.

## Procedural plane — how-to memory

How-to memory (workflows/strategies/worked episodes) is a SEPARATE plane from semantic memory (facts/notes). Route every recall and every write to exactly ONE plane.

<critical_constraint name="procedural_vs_semantic_search">
Recall HOW to do something ("how we deploy", "the release steps") → `memex_procedural_search` ONLY; `memex_memory_search`/`memex_note_search` search the semantic plane and return NO procedures. Recall a FACT / "what is X" / a document → `memex_memory_search`/`memex_note_search` ONLY; never `memex_procedural_search`.
</critical_constraint>

<critical_constraint name="procedural_retrieve_first">
For a task you may have done before (deploy, release, cut/ship a build, bump a version, rotate creds, run a migration, set up an env), check `memex_procedural_search(query="<the task>")` before improvising from the filesystem or memory. A hit is a learned procedure to follow, not re-derive; do not also semantic-search it.
</critical_constraint>

<critical_constraint name="procedural_vs_semantic_add">
Record = exactly ONE write to exactly ONE plane:
- reusable WORKFLOW or WORKED EPISODE ("I did task X, here's how it went"; Trigger/Situation/Actions/Outcome) → `memex_case_submit` and NOTHING ELSE. NEVER also `memex_add_note` (a how-to saved as a note is invisible to the procedural plane — the #1 mistake); never instead of it. Pass `case_of=<id>` when you followed a known procedure.
- FACT / DECISION / DOCUMENT ("what is true") → `memex_add_note` ONLY; never `memex_case_submit`.
There is NO procedure create/update tool — procedures and strategies are DERIVED from the cases you submit. You READ them; the system writes them.
</critical_constraint>

<critical_constraint name="close_the_loop">
When you enact a known procedure (pass `case_of=<id>`), or the user asks to "record" / "log how it went" / "make a record" of a run, close the loop with `memex_case_submit` (set `outcome`) — searching or doing is only half of it. For any other task, apply the capture test: file a case only if you'd want these steps back next time; routine work gets nothing.
</critical_constraint>

<critical_constraint name="consume_skill_hints">
When a procedure's `skill_hints` field lists capability hints, prefer a skill matching each hint before executing the step; the prose action remains authoritative.
</critical_constraint>

<example>"Document how we deploy" → `memex_case_submit`, NOT `memex_add_note` (a how-to note is invisible to the plane).</example>
<example>"What did we decide about retries?" → `memex_memory_search` (fact recall, not how-to).</example>

Two derived kinds, identity anchor `(kind, scope, verb, context)`:
- `procedure` — a workflow; keyed by `verb`+`context` (e.g. verb=`deploy`, context=`nomad`).
- `strategy` — a heuristic over the procedures sharing its `(scope, verb)`; `context` FORBIDDEN.
Search matches `trigger` (when-to-use). Scope: `global` | `project:<id>` | `app:<id>` (no user scope). `memex_case_submit` requires `scope` + `scope_reasoning`; assignment is scoped to that label.

Cases are NOTES (role=`case`), filed by `memex_case_submit` in the hidden case vault to feed derivation. Pinned procedures arrive in your session briefing automatically. `memex_procedural_search` defaults to `status="published"`.

## Claude Code-specific framing

<critical_constraint name="capture_routing">
Before saving, ask: "next time I hit this, would I want these steps back?"
- YES — you worked out HOW to do or fix something non-obvious (a debugging path, a workaround, a sequence that worked) → `memex_case_submit` (trigger, actions, outcome, lesson). Becomes a reusable procedure — not `memex_add_note`.
- NO, but it's a durable FACT / DECISION someone would look up ("we chose X", a config value, an API shape) → `memex_add_note(background=true, author="claude-code")` (≤300 tokens, no per-file changelogs).
- NO to both (it just worked, a typo, a one-off) → save NOTHING. Tie-break: unsure it's worth saving at all → note or nothing; unsure case-vs-note for something how-to-shaped → case.
<example>vitest failed on a stale snapshot cache; clearing `.vitest-cache` fixed it → `memex_case_submit(trigger="vitest fails on stale snapshots", actions=["cleared .vitest-cache"], outcome="success", lesson="clear vitest's cache when tests fail for no code reason")`. "We chose Tailwind v4" → `memex_add_note`; "login UI worked first try" → nothing.</example>
</critical_constraint>

<critical_constraint name="write_routing">
Route each write intent; a miss is silent (no tool call) or wrong-namespace.
- A preference / setting / convention ("I prefer X", "for this repo …", "always lint first") → `memex_kv_put` per the KV namespace rules above (scope by cue; the `<app>` cue beats "I"/"my" — `app:claude-code:*`, not `user:`).
- A reusable workflow or worked episode → `memex_case_submit` (see capture_routing; never `memex_add_note`).
- `"That worked / it's holding / that fixed it"` about an existing memory → `memex_record_outcome(units=[{unit_id, verb:"helpful", reason}])` on the search-returned units; do NOT add a "confirmed" note.
Local `Write`/`Edit` is for project code, never preferences.
</critical_constraint>

<critical_constraint name="clarify_under_ambiguity">
Vague signals — `"that worked"`, `"we did it"`, `"stop suggesting that"` — with NO specific referent → ASK which fix / which suggestion. Never call `memex_record_outcome` with a guessed `unit_id` or a target fabricated from search results.
</critical_constraint>

<critical_constraint name="list_shape_questions">
Recall-shape queries — `"what notes do we have on X?"`, `"remind me about Y"`, `"find anything on Z"`, `"any notes on …"`, `"look for <topic>"` — **enumerate options for the user to pick from**, do NOT deliver the single best answer.

Required:
1. Call `memex_note_search` (or `memex_find_note` / `memex_list_notes`).
2. Present **≥2 candidate notes** as a numbered list.
3. Each entry: `note_key` (or clear descriptor) AND a date reference.
4. Do NOT narrate any single note's contents. Pause for the user to pick.

Detailing the top match — even when it IS the right one — FAILS the intent: they asked to **recognise** which note, and you consumed one for them.

<example>"Find my notes on the deploy pipeline" → list ≥2 with dates and ask which: "1. `ci-cd-circleci-migration` (2025-11-12); 2. `deploy-window-q4-policy` (2025-10-04); 3. `rollback-runbook-revision` (2025-12-01) — which did you mean?" — NOT a narration of the top match.</example>
</critical_constraint>

<critical_constraint name="cooccurrence_graph_required">
Relationship questions (`"who does X work with?"`, `"what cooccurs with Y?"`, `"strongest counterpart"`) REQUIRE `memex_get_entity_cooccurrences` after `memex_list_entities` — the latter returns names but not graph edges, so it can't answer "strongest counterpart" alone.
</critical_constraint>

Slash commands:
- `/remember [text]` — save to memory (routes to `memex_kv_put` / `memex_case_submit` / `memex_add_note` by shape).
- `/recall [query]` — search memory (how-to query → `memex_procedural_search`; else `memex_memory_search` + `memex_note_search`).
- `/learnings` — distill the session's durable learnings; routes each by shape (kv/case/note).
- `/ingest [path|url]` — capture a file/page's content + assets as a note (extraction runs server-side).
- `/lint` — review & resolve memory-hygiene findings (read via MCP, resolve via CLI).
- `/extract-case [note|file|url]` — turn content into a case, if it holds a reusable how-to (gated).
- `/procedure [how-to]` — recall a derived procedure (`memex_procedural_search` / `…_get_by_identity`).
- `/strategy [verb]` — recall the cross-procedure strategy for a verb (`memex_procedural_search(kind="strategy")`).
- `/case [what you did]` — file a worked episode now → `memex_case_submit`; the system derives the procedure.
- `/correct [what's wrong]` — a surfaced memory was wrong/stale → `memex_record_outcome(verb:"not_helpful")` + deprioritize.

Tool hygiene:
- Discovery uses `memex_note_search` / `memex_memory_search` — not `memex_recent_notes` (recency-ordered, not relevance-ranked, so it misses older matches).
- Use only IDs returned by tools; don't fabricate Note/Node/Unit IDs.
- After `memex_note_search`, metadata is inline — skip `memex_get_notes_metadata`.
- For notes over ~500 tokens, read via `memex_get_page_indices` + `memex_get_nodes` (`memex_read_note` errors above that).
- Cite Memex data inline.

<critical_constraint name="answer_from_briefing">
The SessionStart briefing (the `# Session Briefing` block in context) already holds, per vault state: vault summary, themes, top entities, KV facts, pinned procedural cards, and available vaults. Answer overview-shape queries ("what's in this vault", "what's it about") from those sections directly. Call `memex_get_vault_summary` / `memex_kv_list` / `memex_list_vaults` / `memex_survey` only when the relevant section is missing (dropped under budget) or the user wants fresh data.
</critical_constraint>