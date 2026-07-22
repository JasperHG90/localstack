verdict: pass
tree: 40ec8ec5b083d8ccf513df05776c3e1d2b3694d5
pass: architectural
slug: reflection-derives-mechanical-facts
baseline: MANIFESTO.md

# Architectural re-review (cycle 2) — reflection-derives-mechanical-facts

Prior verdict was `pass-with-required-fixes` (fix F1: §2 "State on disk" omitted
`history/`). This pass re-audits at the new tree, confirms the required fix
landed, and confirms nothing regressed. Reviewed the baseline `MANIFESTO.md` in
full and the diff (`git diff HEAD`, HEAD `7c47cad`) independently.

## Tree binding

- `.loop/stamp.json` stamps tree `40ec8ec5b083d8ccf513df05776c3e1d2b3694d5`,
  both gates green (exit 0).
- `loopctl verify` returns `ok`: the current harness fingerprint equals the
  stamped tree. The working tree fingerprints to the bound tree. (Bare
  `git write-tree` differs, as expected, because it does not strip `.loop/`.)

## Required fix F1 — CONFIRMED LANDED

MANIFESTO §2 "State on disk" now enumerates `history/` alongside `verdicts/`,
`reflections/`, and `evals/` (MANIFESTO.md:80-83). The fingerprint sentence
directly below is unchanged and still correct: all of `.loop/` is excluded from
the tree fingerprint EXCEPT `config.json`. `.loop/history/` sits under `.loop/`
and is therefore excluded — the coherent side for churny per-gate-run state.

## Prior passes re-confirmed (no regression)

- **I13 honesty — PASS.** MANIFESTO.md:179-188 states the schema asks only for
  judgment and the mechanical numbers are derived at distill time. Accurate:
  `_REQUIRED_FIELDS = ("slug", "friction", "worked")` (reflection.py:44);
  `distill` derives `cycles` from ledger `review_cycles` and `gates_red` from
  `count_gate_failures` per slug, both authoritative over the body
  (reflection.py:378-380). Enforcer anchor resolves: `verify_reflection(repo,
  slug)` at ctl.py:122.
- **I16 (new invariant) — PASS.** Enforcer `cli.py: _record_gate_failure(repo,
  results, config)` resolves (defined and called from `cmd_stamp` on a
  `StampStatus.RED` verdict). Event carries slug, timestamp, failing commands
  with exit codes, and tree; append-only to `.loop/history/<slug>.jsonl`;
  best-effort (try/except → stderr warning), so it never crashes stamping.
- **Fingerprint coherence with sibling `fingerprint-binds-loop-config` — PASS.**
  `history.py`'s docstring states the log stays out of the fingerprint, which
  binds only `.loop/config.json`. Consistent with I6 and the sibling's
  config-only include-list. `.loop/history/` stays excluded; no self-staling
  deadlock.
- **`history.py` in the module map — PASS.** MANIFESTO.md:70, accurate
  one-line responsibility, coherent with neighbors.
- **No `Stage` growth / no new hook — PASS.** `hooks.py`, `lifecycle.py`, and
  `hooks/hooks.json` untouched; no new `Stage` member; `_ORDER` unchanged.
  Enforcement stays at `finish` via `ctl.done` (R1/S1 grain preserved).
- **Stdlib core — PASS.** `history.py` imports only `datetime`, `json`,
  `pathlib`, plus in-package `stamp.GateResult`. No new runtime dependency.
- **Surgical scope — PASS.** Changed files trace to the ticket surface (§7):
  `reflection.py`, `cli.py`, new `history.py`, `MANIFESTO.md`, tests. The
  `_parse_int` deletion is honest orphan cleanup from removing the numeric
  fields.
- **DECISIONS R5 match — PASS.** DECISIONS.md:38-57 records the schema shrink,
  Q1 (per-slug `.jsonl`), Q2 (full-remove), Q3 (`blockers` stays
  agent-supplied), and Q4 (track `history/`, honored — not in `.gitignore`),
  exactly as implemented.

## Observations (non-blocking; unchanged from cycle 1)

- LOW / informational: §2 disk-state list still omits `.loop/plans/` (relocated
  in commit 1690b2d, before this ticket). Pre-existing doc gap, outside this
  diff and this ticket's contract; noted for the operator, not a fix this pass
  requires.
- LOW / informational: `cli._active_slug` reaches `hooks._ACTIVE_STAGES`, a
  private constant of another core module. `cli` already depends on `hooks`;
  the baseline names no boundary forbidding this. Mild coupling smell, not an
  architectural finding.

## Verdict

pass. The required fix landed, every prior architectural judgment still holds,
invariants and the fingerprint policy are intact, and the working tree
fingerprints to the bound tree `40ec8ec5b083d8ccf513df05776c3e1d2b3694d5`.
