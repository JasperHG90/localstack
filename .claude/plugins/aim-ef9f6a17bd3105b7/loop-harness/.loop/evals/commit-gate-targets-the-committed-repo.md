eval: commit-gate-targets-the-committed-repo

Definition of Done: the commit gate evaluates the repository the
`git commit` actually runs in, resolving a leading `cd <path> &&` prefix
and the `git -C <path> commit` form, instead of the session `cwd`. An
undeterminable target fails safe (blocks) when the session `cwd` is
loop-active; a dormant target no-ops; internal errors still fail open.

Encoded fork resolution (operator to confirm — see ticket §11 Q1):
"undeterminable target → block" is scoped to when the session `cwd` is
itself loop-active. If `cwd` is dormant and the target is unresolvable,
there is no consumer to protect, so the gate allows. `git --git-dir=` /
`--work-tree=` forms are out of scope (Q2): treated as undeterminable.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| `cd` wrong-repo is gated on the target's evidence, not the session's | session repo GREEN; target loop-active with NO green evidence; `cd <target> && git commit -m x` | BLOCK (exit 2) on the target's missing evidence | Deterministic (`test_hooks`, real temp repos) | 100% |
| The `-C` form is detected and gated (was a full bypass) | `git -C <target> commit -m x`, target lacks green evidence | BLOCK (exit 2) | Deterministic (`test_hooks`) | 100% |
| Undeterminable target fails safe when `cwd` is a consumer | unresolvable target form, session `cwd` loop-active | BLOCK (exit 2) + actionable reason on stderr | Deterministic (`test_hooks`) | 100% |
| Undeterminable target no-ops when `cwd` is dormant, Q1 scope | unresolvable target form, session `cwd` has no `.loop/` | ALLOW (exit 0) | Deterministic (`test_hooks`) | 100% |
| A dormant target never gets gated from a consumer session (R4) | `cd <target> && git commit`, target has no `.loop/` | ALLOW (exit 0) | Deterministic (`test_hooks`) | 100% |
| The happy path is preserved (guardrail against over-blocking) | resolved target GREEN (and bound verdicts if mid-flight) | ALLOW (exit 0) | Deterministic (`test_hooks`) | 100% |
| Internal-error fail-open is preserved and distinct from fail-safe (R5) | an unexpected exception in the resolved-repo path | returns 0 (fail OPEN), separately from the fail-SAFE block above | Deterministic (`test_hooks`) | 100% |
| A relative `cd` path resolves against the session `cwd`, not blindly | `cd ../sibling && git commit -m x` from a known `cwd` | evidence read from the resolved sibling dir | Deterministic (`test_hooks`) | 100% |
| Core stays stdlib-only (guardrail) | the diff's imports | `pathlib`/string work only; no new dependency | Deterministic (grep) | 100% |
| End-state matcher reconciled with the sibling ticket | the final `_GIT_COMMIT_RE` / matcher | catches `git commit` and `git -C <path> commit` in command position while ignoring string-data occurrences | Human (adversarial + architectural review) | Must hold |
| Change is surgical and repo gates stay green | `git diff` scope + `loopctl stamp` | only the resolver, the matcher, and `_pre_commit_gate` wiring (plus tests) change; pytest and prek green | Deterministic | 100% |
