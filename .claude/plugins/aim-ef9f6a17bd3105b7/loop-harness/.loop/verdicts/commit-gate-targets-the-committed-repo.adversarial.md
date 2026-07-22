verdict: pass
tree: 946c9445484a9b13128aaadcf7a1eb4522b9be28

# Adversarial review — commit-gate-targets-the-committed-repo (re-bind)

Pass: adversarial. This is a verdict re-bind: the identical code diff was
previously PASSED bound to tree `c4c1e364…`. The repo baseline then advanced by
two unrelated commits (`9ffc261` docs tutorial, `1484ef8` memex build update),
so the verdict is re-issued against the new tree
`946c9445484a9b13128aaadcf7a1eb4522b9be28`. I re-ran every gate on the new
baseline; nothing regressed.

## Premise still sound

The ticket's defect is real and unchanged: a PreToolUse hook fires before the
Bash command runs, so `repo = Path.cwd()` gated the session dir, not the repo
the `git commit` lands in, and `git -C <path> commit` slipped the matcher. The
change resolves the true target and gates that.

## Diff scope traces to the ticket

`git diff HEAD --name-only` shows only:
- `src/loop_harness/hooks.py` (code)
- `tests/test_hooks.py` (tests)
- `.loop/ledger.json`, `.loop/verdicts/*.md` (loop's own bookkeeping written by
  the passes — stage `ready`->`adversarial-review`, verdict pointers; not code
  scope)

The baseline-shift files are correctly excluded: `docs/tutorials/custom-reviews-and-actions.md`
is now tracked at HEAD (baseline), and the memex build update is committed. No
stray files were pulled into the code diff. Every changed source line traces to
the resolver + matcher + `_pre_commit_gate` wiring named in ticket section 7.

## Requirements re-verified against the code

- R1 target resolution — `_resolve_commit_repo` (hooks.py:180-236) walks
  sequencing segments, parses a leading `cd <path> &&` prefix (relative joined
  onto `cwd` via `os.path.normpath`, hooks.py:225-229) and the `git -C <path>
  commit` form (hooks.py:232-234); a bare commit returns `effective`/`cwd`.
  Downstream lookups at hooks.py:409-423 all key off the resolved `repo`.
- R2 `-C` detection — `_git_commit_c_path` (hooks.py:71-124) steps over global
  options and reports `commit` as the subcommand; `_invokes_git_commit` now
  routes through it (hooks.py:172). Test flips `("git -C other commit -m x",
  True)` (test_hooks.py:62). Against old code (post-sibling pairwise git/commit
  adjacency) this token sequence has no adjacent git,commit pair, so old
  returned False; new returns True. Genuine reproducing assertion.
- R3 fail-safe scoped to a live consumer — on `repo is None`, block (exit 2)
  only when `loop_active(cwd) and halt_mod.engaged(cwd) is None`, else return 0
  (hooks.py:395-408). Matches the eval fork resolution (undeterminable blocks
  only when `cwd` is loop-active; dormant `cwd` no-ops; HALT bypasses).
  Actionable stderr message present.
- R4 dormancy on resolved target — `if not loop_active(repo): return 0`
  (hooks.py:409). `test_gate_dormant_target_is_not_gated_from_a_consumer`
  covers a non-consumer target reached from a green consumer session, exit 0.
- R5 internal-error fail-open — outer `try/except` returns 0 (hooks.py:425-427);
  `test_gate_internal_error_still_fails_open` monkeypatches the resolver to
  raise and asserts exit 0, kept distinct from the fail-safe block in
  `test_gate_undeterminable_target_fails_safe_from_a_consumer`.

## Restrictions honored

- Stdlib-only: the only new import is `os` (stdlib); `pairwise` removed as
  now-unused. No `uv add`, no new dependency. Confirmed against the eval grep
  guardrail.
- Numpy docstrings on both new helpers (`_git_commit_c_path`,
  `_resolve_commit_repo`) with Parameters/Returns sections.
- Tests use real temp git repos under `tmp_path` with `monkeypatch.chdir` and
  stdin JSON payloads driven through `hooks.main(["pre-commit-gate"])` — no git
  layer mocking. Reproducing tests present for both the `cd` wrong-repo and
  `-C` bypass holes.

## Would-fail-against-old-code check

- `test_gate_cd_prefix_gates_the_target_not_the_session`: old code gated
  `Path.cwd()` (green session), allow(0); new asserts block(2) on the target's
  missing stamp. Fails on old, passes on new. Valid.
- `test_gate_dash_C_form_is_detected_and_gated`: old matcher never fired on the
  `-C` form, allow(0); new asserts block(2). Valid.

## Gates (re-run on the new baseline)

- `git add --intent-to-add -A . && uv run pytest` -> 228 passed.
- `uvx prek run --all-files` -> ruff-lint, ruff-format, mypy all Passed.

No confirmed findings. Nothing regressed under the baseline shift. PASS,
re-bound to tree 946c9445484a9b13128aaadcf7a1eb4522b9be28.
