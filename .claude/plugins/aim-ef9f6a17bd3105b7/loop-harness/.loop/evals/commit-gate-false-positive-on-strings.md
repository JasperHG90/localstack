eval: commit-gate-false-positive-on-strings

Definition of Done: a Bash command is gated as a commit only when it
genuinely invokes `git commit` as a subcommand. "git commit" appearing as
string data (an echo argument, a `--grep`/`-m` value, or a leading `#`
comment) is never gated, while every real commit the suite pins today,
including compound forms, stays gated.

Encoded fork resolutions (operator to confirm — see ticket §11): Q1 a
shlex parse failure falls back to the old substring regex for that command
only (still gates, fail-safe direction); Q2 sequencing operators are split
by regex so `git add&&git commit` without spaces still gates; Q3 only a
segment-leading `#` is stripped, so `-m "fix #42"` is preserved.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| "git commit" in an echo argument is not gated | `echo "=== all git commit subjects ==="` | `allow=True`, empty message | Deterministic (`test_hooks`) | 100% |
| "git commit" in a `--grep` value is not gated | `git log --grep="git commit"` | `allow=True`, empty message | Deterministic (`test_hooks`) | 100% |
| A leading `#` comment mentioning git commit is not gated | `# git commit here later` | `allow=True`, empty message | Deterministic (`test_hooks`) | 100% |
| A bare real commit is still gated (guardrail) | `git commit -m 'x'` with no green stamp | gate engages → `allow=False` | Deterministic (`test_hooks`) | 100% |
| A compound real commit is still gated (guardrail) | `git add -A && git commit -m 'y'` | gate engages → `allow=False` | Deterministic (`test_hooks`) | 100% |
| An operator-glued commit still gates, Q2 (guardrail) | `git add&&git commit -m 'z'` | gate engages → `allow=False` | Deterministic (`test_hooks`) | 100% |
| A commit message containing `#` is not truncated, Q3 | `git commit -m "fix #42"` | gate engages → `allow=False` (message intact) | Deterministic (`test_hooks`) | 100% |
| A malformed-quote real commit fails toward the gate, Q1 | `git commit -m "oops` | still `allow=False` via the regex fallback | Deterministic (`test_hooks`) | 100% |
| Both call sites share one predicate, no drift | Read `hooks.py:151` and `hooks.py:223` | both call the same `_invokes_git_commit` helper | Human review | Must hold |
| Core stays stdlib-only (guardrail) | The diff's imports | only `shlex` (stdlib) added; no third-party parser | Deterministic (grep) | 100% |
| `-C` parity is preserved (sibling owns it) | `git -C other commit -m x` | NOT newly matched by this ticket's change | Deterministic (`test_hooks`) | 100% |
| Change is surgical and repo gates stay green | `git diff` scope + `loopctl stamp` | only the detector helper and its two call sites (plus tests) change; pytest and prek green | Deterministic | 100% |
