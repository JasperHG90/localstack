verdict: pass
tree: 946c9445484a9b13128aaadcf7a1eb4522b9be28

# Architectural review: commit-gate-targets-the-committed-repo

Pass: architectural (loop-architect). Baseline: `MANIFESTO.md`.

Verdict re-bind. This exact code diff previously PASSED architecturally bound
to tree `c4c1e364…`. The repo baseline then advanced (two unrelated commits:
a committed tutorial under `docs/tutorials/` plus a ledger/verdict landing),
so the verdict is re-bound to the new tree `946c9445…`. The code diff
(`src/loop_harness/hooks.py`, `tests/test_hooks.py`) is unchanged. Nothing
in the two baseline commits touches the code surface this ticket edits or the
invariants it implicates. No regression.

## Diff scope confirmation

`git diff HEAD` touches: `src/loop_harness/hooks.py`, `tests/test_hooks.py`,
and `.loop/` bookkeeping (`ledger.json`, the two `verdicts/*.md`). The
`.loop/` directory is stripped from the tree fingerprint (MANIFESTO §2
lines 79-83; I6), so it never enters the certified tree. No `docs/tutorials/`
entry appears in the diff (the new tutorial is committed baseline, not part
of this change). No stray baseline code files entered the diff. Confirmed.

## Invariant checks

- **I7 — commit gate refuses commits without earned evidence (strengthened).**
  Upheld. `_pre_commit_gate` now resolves the committed repo via
  `_resolve_commit_repo(command, cwd)` (`hooks.py:394`) and keys every
  evidence lookup (dormancy, ledger, stamp, tree, verdicts) off the resolved
  target rather than `Path.cwd()`. The `-C` form is detected: `_git_commit_c_path`
  steps over global options and extracts a `-C <path>` target
  (`hooks.py:_git_commit_c_path`), and `_invokes_git_commit` now gates it
  (test `git -C other commit -m x` → True). The enforcer anchor
  `def decide_commit_gate(` is unchanged and still receives resolved evidence.
  HALT remains the sole bypass (`halt_mod.engaged(repo)` on the normal path;
  `halt_mod.engaged(cwd)` on the undeterminable path).

- **Fail-safe vs fail-open split (MANIFESTO lines 30-32; I8; value "Hooks
  fail open on internal error", lines 200-202).** Upheld and correctly kept
  distinct. A resolvable-command-but-undeterminable target (`repo is None`)
  BLOCKS (exit 2) when the session `cwd` is loop-active and not halted
  (`hooks.py:395-408`) — a policy ambiguity failing safe toward more checking,
  scoped to an actual consumer per the ticket §11 fork. An internal exception
  during resolution is caught by the outer `try/except` (`hooks.py:425-427`)
  and fails OPEN (exit 0). Tests exercise both paths independently
  (`test_gate_undeterminable_target_fails_safe_from_a_consumer` for the block,
  `test_gate_internal_error_still_fails_open` for the open), so the two are
  not conflated.

- **Dormancy on the resolved target (R4; module docstring lines 8-10).**
  Upheld. `if not loop_active(repo): return 0` (`hooks.py:409`) is evaluated
  against the resolved target, so a non-consumer target no-ops even from a
  consumer session, and the undeterminable branch guards on `loop_active(cwd)`.
  Covered by `test_gate_dormant_target_is_not_gated_from_a_consumer` and
  `test_gate_undeterminable_target_noops_from_a_dormant_cwd`.

- **Stdlib-only core (MANIFESTO lines 197-199, "Dependency-free core").**
  Upheld. The change adds only `import os` (stdlib) and drops
  `from itertools import pairwise`; resolution is `shlex`/`pathlib`/`os.path`
  string work. No new third-party dependency.

- **`decide_commit_gate` purity (ticket §5; I7 enforcer).** Upheld. The pure
  policy function's signature is untouched; repo resolution lives upstream in
  `_pre_commit_gate`. `decide_commit_gate` still operates over already-resolved
  evidence and does not resolve the repo.

- **Surgical scope / simplicity (values, lines 203-207).** Upheld. Changes
  trace to the defect: a target resolver, a token-aware `-C`/subcommand
  classifier, and the wiring at the former `Path.cwd()` site. No adjacent gate
  logic refactored; no speculative shell grammar (unmodeled forms →
  undeterminable → fail safe).

- **Tests ship with the code (value, lines 209-211).** Upheld. Real temp git
  repos under `tmp_path`, driven through `hooks.main(["pre-commit-gate"])`;
  reproducing cases for both the `cd` wrong-repo and `-C` bypass holes plus
  fail-safe, fail-open, dormancy, HALT-bypass, and happy-path coverage.

## Baseline silence

The MANIFESTO does not prescribe a shell-parsing strategy or the exact
boundary of "undeterminable"; those are ticket-level (§11) operator decisions,
not baseline rules. No architectural rule speaks to them, so I raise no
finding there.

## Gate status

Not re-run by this pass (the adversarial pass owns gate re-runs). Confirmed
non-mutatingly that `uv run pytest tests/test_hooks.py` is green (71 passed).
The adversarial verdict records both gates green (228 passed; ruff + mypy
pass).

## Findings

None. No architectural rule, invariant, or boundary is eroded. PASS.
