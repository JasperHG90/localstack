# Architectural verdict: commit-gate-git-hook-backstop (cycle 2)

verdict: pass
tree: e5a8c7a689c6b631c5640cf193c68bcd006b8b52

Baseline: `MANIFESTO.md`. Pass: `architectural` (loop-architect).
HEAD: `8be08fca99f268f050fcdf7b0fd95ba69ac009c5`. Diff scope: `git diff HEAD`.

## Summary

The two required fixes from cycle 1 (pass-with-required-fixes) are landed and
accurate. The baseline now describes the architecture the diff implements: the
§2 module map lists `githook.py`, and I7 names both enforcement points sharing
the one `decide_commit_gate` policy. Both enforcer anchors resolve to real code.
No prior-confirmed conformance regressed. The working tree fingerprints to the
bound tree.

## Verification of the cycle-1 required fixes

### Fix 1 — §2 module map now lists `githook.py` (RESOLVED)

`MANIFESTO.md:67` adds the row:
`| githook.py | The optional git-level pre-commit backstop: a second
enforcement of the commit gate git itself runs, reusing the one policy. |`
This matches the new module `src/loop_harness/githook.py` and its stated
responsibility (a second enforcement reusing the single policy). The map no
longer omits a first-class module. Accurate.

### Fix 2 — I7 names both enforcement points and cites both anchors (RESOLVED)

`MANIFESTO.md:140-149` (I7) now states a commit is allowed only on green
evidence, HALT is the sole bypass, and "Two enforcement points share the one
`decide_commit_gate` policy so they cannot drift: the `git commit` PreToolUse
hook ... and an optional git-level `pre-commit` backstop that git itself runs."
The enforcer line reads:
`hooks.py: def decide_commit_gate( (reused by githook.py: def pre_commit()`.

Both anchors resolve against the bound tree:
- `src/loop_harness/hooks.py:288` — `def decide_commit_gate(`
- `src/loop_harness/githook.py:191` — `def pre_commit() -> int:`

The prose is accurate to the code: `githook.py:214` calls `decide_commit_gate`
with a canonical `"git commit"` command (I7 policy reuse, no drift), and the
"a string matcher cannot see (a subprocess, `eval`, or a human at the
terminal)" phrasing matches the ticket's §3 gap classes.

## No regression on prior-confirmed conformance

- Single policy, no drift (I7 / ticket R2): the git entry reuses
  `decide_commit_gate` verbatim (`githook.py:214-223`) plus the config
  fail-safe helpers `enabled_passes_failsafe` / `fingerprint_ignore_failsafe`
  imported from `hooks.py`. No evidence rules are reimplemented. Confirmed.
- Fail-open vs fail-safe split (MANIFESTO §1 lines 30-32; I8; the "Hooks fail
  open on internal error" value at lines 240-243): a genuine no-evidence state
  returns `1` to block (`githook.py:229-230`), while the outer `except`
  returns `0`, printing "failing open" to stderr (`githook.py:224-226`). The
  split is intact at the second enforcement point. Confirmed.
- Stdlib-only core (MANIFESTO §2 lines 40-42; "Dependency-free core" value
  lines 237-239): `githook.py` imports only `stat`, `subprocess`, `sys`,
  `dataclasses`, `pathlib`, and internal `loop_harness` modules. No new
  third-party dependency. Confirmed.
- Surgical scope (value lines 244-246): the MANIFESTO change is confined to the
  §2 map row and the I7 block; `decide_commit_gate`, the string matcher, and
  the PreToolUse entry are untouched. Confirmed.

## Tree binding

Independently recomputed
`tree_fingerprint(repo, fingerprint_ignore_failsafe(repo))`
= `e5a8c7a689c6b631c5640cf193c68bcd006b8b52`, matching `.loop/stamp.json` and
the bound tree; `loopctl verify` reports `ok`.

## Gates (independently re-run)

- `git add --intent-to-add -A . && uv run pytest` — all tests passed.
- `uvx prek run --all-files` — ruff-lint, ruff-format, mypy all Passed.

## Findings

None. No architectural violation, no eroded invariant.
