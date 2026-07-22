eval: commit-gate-git-hook-backstop

Definition of Done: git itself refuses a commit lacking green tree-bound
evidence regardless of how the commit is spelled or who issues it, without
clobbering an existing hook or wedging commits on a harness bug.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Git blocks a matcher-blind commit with no evidence (the gap) | Installed hook; loop-consumer repo with no green stamp; commit via `git -C <repo> commit` issued from elsewhere | Git exits non-zero and refuses the commit, reason on stderr | Deterministic (`test_*`) | 100% |
| Git blocks a subprocess/substitution commit (the gap) | Installed hook; no evidence; `python -c "subprocess.run(['git','commit',...])"` | Git refuses the commit | Deterministic (`test_*`) | 100% |
| Green evidence passes | Installed hook; green stamp and every enabled pass's tree-bound verdict on the current tree | `git commit` succeeds through the hook | Deterministic (`test_*`) | 100% |
| HALT steps the git hook aside (R3) | `.loop/HALT` engaged; no green evidence | The commit succeeds (operator in control) | Deterministic (`test_*`) | 100% |
| Dormant repo no-ops (R4) | A repo without `.loop/` (install never ran, or `.loop/` removed) | An ordinary commit is unaffected | Deterministic (`test_*`) | 100% |
| Internal error fails OPEN (guardrail) | A monkeypatched raise in the hook's evidence path | The commit is ALLOWED, not wedged | Deterministic (`test_*`) | 100% |
| Install never clobbers an existing hook (guardrail) | Install into a repo with an existing `pre-commit` hook or a set `core.hooksPath` | Install refuses-and-warns; the pre-existing hook is intact | Deterministic (`test_*`) | 100% |
| Uninstall restores prior state; install is idempotent | Install, then `uninstall`; separately, install twice | Prior state restored; re-install stacks no duplicate hook | Deterministic (`test_*`) | 100% |
| Policy parity with the PreToolUse gate (guardrail) | The same evidence state fed to both enforcement points | The git hook and the PreToolUse gate produce the same allow/block outcome | Deterministic (`test_*`) | 100% |
