eval: reflection-derives-mechanical-facts

Definition of Done: the reflection's mechanical numbers are derived from
recorded evidence rather than agent self-report, the repo remembers gate
failures, and the agent supplies only judgment.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| The repo remembers gate failures | Drive a ticket RED three times then GREEN through the stamp path | `.loop/history/<slug>.jsonl` holds exactly 3 events, each carrying slug, timestamp, failing command(s) with exit codes, and the tree | Deterministic (`test_*`) | 100% |
| A GREEN stamp appends nothing (guardrail) | A single GREEN `loopctl stamp` run | No event is appended to the history log | Deterministic (`test_*`) | 100% |
| Derivation ignores the body (anti-self-report) | Ledger `review_cycles` = C and a log of N events; the reflection body omits or states contradictory numbers | `distill` reports `cycles == C` and `gates_red == N` for that slug | Deterministic (`test_*`) | 100% |
| Shrunk schema validates with judgment only | A reflection carrying only `slug`, `friction`, `worked` (plus optional `harness_change`) and prose | Parses VALID with no `cycles`/`gates_red` present | Deterministic (`test_*`) | 100% |
| Old-schema reflections still parse (guardrail, R-D) | A committed reflection still carrying `cycles:` and `gates_red:` | Parses VALID; `distill` uses the derived numbers and ignores the stale self-reported ones | Deterministic (`test_*`) | 100% |
| Scaffold emits no numeric fields | `scaffold_reflection` output | No `cycles:` or `gates_red:` line; the output re-parses VALID | Deterministic (`test_*`) | 100% |
| A RED-stamp append never crashes stamping (guardrail) | The history append path raises (e.g. an unwritable `.loop/history/`) | The stamp verdict is still returned; stamping does not abort | Deterministic (`test_*`) | 100% |
| The history log stays out of the fingerprint (guardrail) | After a green stamp, append a gate-failure event under `.loop/history/` | `verify_stamp` stays `OK`; the log does not stale the stamp | Deterministic (`test_*`) | 100% |
