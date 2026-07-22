# Adversarial verdict: commit-gate-git-hook-backstop (re-review, cycle 2)

verdict: pass
tree: e5a8c7a689c6b631c5640cf193c68bcd006b8b52

## Scope of this re-review

The ONLY change since the prior PASS (tree `a35d44b`) is a documentation
edit to `MANIFESTO.md` — the architectural pass's required fix. No code
changed. I re-ran both gates independently at the new bound tree, verified
the MANIFESTO edit introduces no inaccuracy (both enforcer citations
resolve to real code), and re-confirmed every prior code finding still
holds.

## Tree binding

- `loopctl verify` = ok; `.loop/stamp.json` binds
  `e5a8c7a689c6b631c5640cf193c68bcd006b8b52`, matching the briefing.
- HEAD `8be08fca99f268f050fcdf7b0fd95ba69ac009c5`. `loopctl verify` still
  ok after `git add --intent-to-add` (tree object unchanged).

## Gates re-run independently — GREEN

- `git add --intent-to-add -A . && uv run pytest` — full suite green,
  0 failures.
- `uvx prek run --all-files` — ruff-lint Passed, ruff-format Passed,
  mypy Passed.

## MANIFESTO edit — accurate, both citations resolve

The doc diff is confined to two locations, both outside `aim:` markers:

1. §2 module map adds a `githook.py` row: "The optional git-level
   `pre-commit` backstop: a second enforcement of the commit gate git
   itself runs, reusing the one policy." `src/loop_harness/githook.py`
   exists. Accurate: install is explicit/optional (`githook.py:112`),
   git-run, and reuses the one policy.
2. I7 is rewritten to name both enforcement points and closes with
   `**Enforcer:** hooks.py: def decide_commit_gate( (reused by githook.py:
   def pre_commit()`.
   - `def decide_commit_gate(` resolves: `hooks.py:288`.
   - `def pre_commit(` resolves: `githook.py:191`.
   - The prose ("Two enforcement points share the one `decide_commit_gate`
     policy so they cannot drift ... closing the commits a string matcher
     cannot see (a subprocess, `eval`, or a human at the terminal)")
     matches ticket §3's three matcher-blind classes and R1/R2.

No hallucination, no identity leak, no stub, no em-dash or slop
introduced. The edit traces directly to R1 (strengthen I7 with an actor-
and spelling-independent enforcement point); in scope.

## Prior code findings — re-confirmed (no code changed)

- Core promise: `pre_commit` (`githook.py:191`) keys evidence to
  `Path.cwd()` and reuses `decide_commit_gate` via a canonical
  `"git commit"` command (`githook.py:214-223`); it never relies on a
  Bash command string, so it catches the §3 subprocess / `eval` / human
  classes. Blocks with exit 1 + stderr on no-evidence
  (`githook.py:229-230`) — fail-safe.
- Fail direction: evidence assembly and the policy call are inside the
  try; the allow/block translation is outside (`githook.py:206-230`). Any
  internal exception returns 0 (allow) at `:224-226` — fail-OPEN, cannot
  wedge a commit over a harness bug.
- Never-clobber (R6): `install` refuses on a set `core.hooksPath`
  (`githook.py:133-140`) and on an unmanaged existing hook (`:145-153`);
  `uninstall` leaves an unmanaged hook untouched (`:182-186`).
- Dormancy (R4): `loop_active` short-circuit (`githook.py:208`).
- HALT parity (R3): `halt_mod.engaged(repo)` fed to the policy
  (`githook.py:216`).
- Policy reuse (R2): `decide_commit_gate` signature and body untouched.

## Verdict

pass. Both gates are green on the bound tree, the MANIFESTO documentation
edit is accurate with both enforcer citations resolving to real code, and
all prior code findings still hold. No code changed since the prior PASS.
