verdict: pass
tree: 90b8d848e8f0044348296223dfafd9a28b210360

# Architectural review: reconcile-registers-orphan-plans (cycle 2)

Pass: architectural pass (loop-architect) against `MANIFESTO.md`.
Baseline: `MANIFESTO.md`. Settled forks: `DECISIONS.md` section P.
Bound tree verified: `loopctl verify` returns `ok`; `.loop/stamp.json`
carries `90b8d848e8f0044348296223dfafd9a28b210360` with both gates exit 0;
an independent `tree_fingerprint(repo)` recompute yields the same 40-hex.
HEAD `8cf1012`.

## Summary

Re-review after the cycle-1 LOW honesty nit (I17 reverse-warning clause
omitting `blocked`) was fixed. The change upholds every architectural rule
the baseline states. I17's prose now matches its enforcer, so the prior
I17-vs-P3 inconsistency is gone. The closed `Stage` enum stays closed,
enforcement is reconcile (not a write-time hook), the shared-home hazard is
contained, the single ledger write path is preserved, and the core is
stdlib-only. DECISIONS section P (P1-P6) matches the implementation. One new
LOW-severity, non-blocking finding on baseline module-map completeness.

## Cycle-1 nit — RESOLVED

I17 now reads "an active entry (not `done`, `blocked`, or dropped) whose plan
vanished only warns" (`MANIFESTO.md:224`). The enforcer scopes the
reverse-orphan warning away from exactly those states:
`_NO_REVERSE_WARNING = frozenset({Stage.DONE, Stage.BLOCKED})` (reconcile.py:19)
plus the `entry.dropped` guard in the reverse loop
(`if entry.dropped or entry.stage in _NO_REVERSE_WARNING: continue`).
I17 prose, the `reconcile_plans` docstring ("UNLESS it is terminal (`done`),
`blocked`, or `dropped`"), and DECISIONS P3 ("`done`/`blocked`/`dropped`
entries are silent") now agree. Confirmed fixed.

## Judged points

### Closed-enum grain (I1 / R1 / S1 / P6) — UPHELD
`Stage` retains exactly eight members (`ready…done`, `blocked`), no
`Stage.DROPPED` (ledger.py:22-32); `_ORDER` and lifecycle branches are
untouched. Drop is an orthogonal `dropped: bool = False` (ledger.py:66),
serialized in `to_dict` (ledger.py:82) and tolerantly read in `from_dict`
(`dropped=bool(raw.get("dropped", False))`, ledger.py:102), so pre-existing
ledgers load unchanged. This is the P6 resolution of Q7 and honors the
"enforce at an existing point, do not grow the state machine" grain
(MANIFESTO §5, R10). Confirmed.

### I17 enforcer resolves — UPHELD
The Enforcer line cites
`def reconcile_plans(repo: Path, ledger: Ledger, config: LoopConfig) -> tuple[list[str], list[str]]:`,
present verbatim. Load-bearing claims hold: registration keys on plan-file
existence (`ledger.entries[slug] = TicketEntry(slug=slug)` when
`slug not in ledger.entries`), a `dropped` entry stays in the ledger and is
never re-registered (R4), `register` clears the flag (ctl.py un-drop path),
and reconcile never deletes an entry (the reverse pass only appends
warnings). Confirmed.

### Strengthened I11 — HONEST
I11's Enforcer still cites the unchanged
`def reconcile(repo: Path, ledger: Ledger) -> list[Correction]:`, which
resolves. The added sentence ("The plans pass (I17) runs first…") matches the
ordering at both call sites: `reconcile.main` and `hooks._session_start` each
call `reconcile_plans` before the git pass, so a self-healed orphan lands
`done` in one run. Confirmed.

### Reconcile is enforcement, not a hook (DECISIONS P1) — UPHELD
No PostToolUse or any write-time registration hook was added.
`_session_start` (hooks.py:443+) calls `reconcile_plans` then
`reconcile_git`; the plans pass keys on plan-file existence, so a missed
registration is recoverable on the next run and via `loopctl register`.
Matches P1 and the ticket non-goal rejecting a write-time hook. Confirmed.

### Single write path / state discipline (I10) — UPHELD
The ledger changes only through harness code: `ctl.register`/`ctl.drop` and
`_session_start` persist via `save_ledger`. `drop` is a new blessed
transition added inside `ctl.py`, keeping ctl.py the transition write path;
reconcile writing the ledger is the baseline-sanctioned second writer (module
map). No Edit/Write to `ledger.json`; the state guard (`decide_state_guard`)
is untouched. Matches I10 and P5/Q6. Confirmed.

### Containment (DECISIONS P4 / R6) — UPHELD
`resolve_plans_dir` expands `~`, resolves relative paths against the repo
root, and returns `None` unless `resolved == repo_root or repo_root in
resolved.parents`; `reconcile_plans` no-ops on `None`. The shared-home
default `~/.claude/plans` yields `None` and registers nothing. Correct
boundary for the shared-home hazard. Confirmed.

### Drop is reversible, stage-preserving (R11 / P6) — UPHELD
`ctl.drop` sets `dropped = True` without touching `stage`; `ctl.register` on
a dropped slug clears the flag and returns without altering `stage`, so an
un-drop restores the pre-drop lifecycle position. Confirmed.

### Stdlib-only core, surgical scope — UPHELD
New imports are stdlib (`contextlib` in hooks.py) or intra-package
(`loop_harness.config`, `loop_harness.reconcile`). No third-party import
added. Changed source lines trace to the ticket's code surface (§7); the
`"dropped": false` addition across every `ledger.json` entry is the expected
serialization of the new field. Confirmed.

### DECISIONS section P matches implementation — UPHELD
P1 (reconcile not write-time hook), P2 (auto-register at `ready`, path
derived from slug), P3 (reverse warn scoped to non-terminal/non-dropped;
done/blocked/dropped silent), P4 (repo-contained only), P5 (both call sites,
SessionStart persists), P6 (`dropped: bool`, not a `Stage` member) each map to
the code. Confirmed.

## Findings (LOW severity, non-blocking)

L1. Baseline module-map enumeration omits the new `drop` write verb.
MANIFESTO §2, `MANIFESTO.md:63`: "`ctl.py` | The only supported ledger write
path (register / advance / block / done)." This change adds a fifth blessed
ctl transition, `drop`, but the parenthetical was not extended. The core
claim (ctl.py is the only supported write path) still holds and `drop` was
correctly placed inside ctl.py, so no invariant or boundary is eroded; the
illustrative list is merely incomplete. Baseline rule touched: MANIFESTO §2
module map as current-state authority. The same omission appears in the
`cli.py` module docstring (cli.py:4-5), which lists "register, advance,
block, done, finish" and drops `drop` — ticket §7 asked for that docstring
update; this is documentation completeness the adversarial pass owns. Both
are optional tidy-ups, not required for pass.

## Verdict
pass — architecture fully upheld and the cycle-1 I17 honesty nit is fixed.
The working tree fingerprints to the bound tree
`90b8d848e8f0044348296223dfafd9a28b210360`. One LOW-severity, non-blocking
module-map/docstring completeness finding (L1) that erodes no invariant or
boundary.
