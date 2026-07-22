verdict: pass
tree: 90b8d848e8f0044348296223dfafd9a28b210360

# Adversarial re-review (cycle 2): reconcile-registers-orphan-plans

Re-audited at tree `90b8d848e8f0044348296223dfafd9a28b210360`. `loopctl
verify` returns `ok` and `.loop/stamp.json` carries this exact tree with both
gates at exit 0. I independently re-ran both gates:

- `git add --intent-to-add -A . && uv run pytest`: all tests passed.
- `uvx prek run --all-files`: ruff-lint, ruff-format, mypy all Passed.

The prior verdict was pass-with-required-fixes. Every required and
recommended item is now resolved, and nothing previously passing regressed.

## Required fix from cycle 1 — landed and genuine

The R7 self-heal ordering test now exists:
`tests/test_reconcile.py:135` `test_reconcile_plans_then_git_self_heals_committed_orphan`.
It genuinely exercises the ordering, not a stub. It writes a real plan file
(`healed-x.md`), makes a real slug-anchored commit (`_commit`,
`tests/test_reconcile.py:154`), starts from an empty ledger, runs the plans
pass (asserts `registered == ["healed-x"]` at `ready`), then runs the git
pass and asserts the entry lands `Stage.DONE`. The order is load-bearing:
`reconcile` (`reconcile.py:57`) only iterates entries already in the ledger,
so if the git pass ran first on the empty ledger it would find nothing to
upgrade and `healed-x` would settle at `ready`. Plans-before-git is what
produces `done` in one pass. `main` (`reconcile.py:161-164`) and
`_session_start` (`hooks.py:446-454`) both call `reconcile_plans` before
`reconcile_git`, matching the sequence the test proves.

## Recommended coverage from cycle 1 — landed

- `test_reconcile_plans_silent_on_blocked_missing_plan`
  (`tests/test_reconcile.py:114`): a `blocked` entry with no plan yields no
  warning. Closes the ticket test-2 `blocked` variant gap.
- `test_reconcile_plans_absent_dir_is_noop` (`tests/test_reconcile.py:123`):
  a configured-but-absent `plans_dir` is a clean no-op, guarding the
  `not plans_dir.is_dir()` branch (`reconcile.py:134`). Closes the ticket
  test-7 absent-dir gap.

## MANIFESTO I17 wording — now matches code

I17 (`MANIFESTO.md:215`) reads "an active entry (not `done`, `blocked`, or
dropped) whose plan vanished only warns." The suppression in `reconcile_plans`
is `if entry.dropped or entry.stage in _NO_REVERSE_WARNING` with
`_NO_REVERSE_WARNING = frozenset({Stage.DONE, Stage.BLOCKED})`
(`reconcile.py:23,142`). Wording and code agree; the enforcer line points at
the real signature.

## Prior passing findings — re-confirmed at this tree

- Anti-resurrection (R4): `reconcile_plans` registers only slugs ABSENT from
  the ledger (`reconcile.py:138`); a dropped entry with a surviving plan is
  skipped. Pinned by `test_reconcile_plans_never_resurrects_dropped`
  (`tests/test_reconcile.py:96`).
- Containment (R6/Q5): `resolve_plans_dir` (`reconcile.py:87`) does
  expanduser + repo-relative resolve + `.resolve()` normalization, then
  `resolved == repo_root or repo_root in resolved.parents` (a path-component
  test, not a string prefix). Symlink/`..` defeats canonicalize outside and
  return `None`. Pinned by `test_reconcile_plans_ignores_shared_home_plans_dir`
  (`tests/test_reconcile.py:81`).
- Never-deletes: the reverse pass only appends warning strings
  (`reconcile.py:145`); no entry is ever removed.
- Idempotency (R2/R3): `test_reconcile_plans_is_idempotent`
  (`tests/test_reconcile.py:71`) and `register` no-op on a present,
  non-dropped slug (`ctl.py:52`, `test_register_present_non_dropped_is_noop`).
- Fail-safe: `ConfigError` suppressed in both `main` (`reconcile.py:162`) and
  `_session_start` (`hooks.py:450` `contextlib.suppress(ConfigError)`), with
  `reconcile_git` running unconditionally afterward and the whole hook body
  wrapped in try/except returning 0. Fail-open confirmed.
- Serialization: `dropped` defaults `False`, and `from_dict` reads it tolerant
  of absence (`bool(raw.get("dropped", False))`, `ledger.py:102`), so old
  ledgers load unchanged.

## Drop (shape A) — consistent with §11 / DECISIONS P6

`dropped: bool` field on `TicketEntry` (`ledger.py:66`); closed `Stage` enum
untouched; `lifecycle.py` unchanged. `ctl.drop` marks in place and raises on
an absent slug (`ctl.py:58`); `ctl.register` clears the flag on a dropped slug
and preserves stage (`ctl.py:47-52`). `loopctl drop` wired (`cli.py`).
DECISIONS.md section P records the chosen shape and settled forks (R12).
Covered by the `tests/test_ctl.py` drop / un-drop / no-op / stage-preservation
tests, each of which fails against the old code (the `drop` symbol and
`dropped` field did not exist).

## Scope

The `.loop/ledger.json` diff is exactly the additive `"dropped": false` field
serialized on every entry plus the review ticket's own `ready ->
adversarial-review` lifecycle advance (slug `reconcile-registers-orphan-plans`,
attempts 1, review_cycles 1) — harness bookkeeping, no stray stage mutation on
any other entry. Every changed source line traces to the ticket. Doc edits
(MANIFESTO I17 + I11, DECISIONS P, create-ticket mandatory register step) map
to R9/R12 and carry real enforcer lines. No unrelated refactoring.

## Non-blocking observation (informational, no fix required)

`_DONE_STAGES` includes `Stage.COMMIT` but `_NO_REVERSE_WARNING` does not, so
an entry momentarily at `commit` with a missing plan would emit a
reverse-orphan warning. This follows the letter of R5 and I17 (which name
`done`, not the transient `commit`), and in practice a `commit`-stage plan
file still exists, so no spurious warning arises. Recorded for awareness, not
a defect against the contract.

Verdict: pass.
