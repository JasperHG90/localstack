# Architectural review: stamp-fingerprint-ignore-list (re-run)

verdict: pass
tree: f07318510134bcbf3f5b0d8bee9bba9c24528de3

Baseline: `MANIFESTO.md` (present, read in full). Ticket:
`stamp-fingerprint-ignore-list`. This pass judges conformance to the
architecture, not gate re-execution or line-level correctness (the
adversarial reviewer owns those).

Scope of this re-run: two follow-up changes landed since the prior PASS
(tree fd1c0bef). Verified neither disturbs an invariant validated last
round, and that the README addition is consistent with the project's docs.
Reviewed the actual code and baseline, not the hand-off summary.

## What changed since the prior PASS

Follow-up 1: `load_config` now rejects empty/whitespace-only
`fingerprint_ignore` patterns (`config.py:235-240`).
Follow-up 2: docstring corrections (`tree_fingerprint`,
`LoopConfig.fingerprint_ignore`) and a new README section. The core
mechanism (single `tree_fingerprint`, subtract-only, all callers thread the
config-resolved list, `fingerprint_ignore_failsafe` -> `()` on ConfigError)
is unchanged and re-confirmed below.

## Invariant conformance (all upheld)

### I3 — single definition of the fingerprint (MANIFESTO:107-110; ticket §6)
`tree_fingerprint` remains the one function every reader calls. The
follow-ups touched only config validation, docstrings, and the README; the
signature `tree_fingerprint(repo, ignore=())` and the subtract-only `git rm`
loop are untouched. All callers still thread the same config field:
`ctl.py:70,72`, `cli.py:44,46`, `hooks.py:235,240`, and the internal
`write_stamp`/`verify_stamp`; `stamp.main` resolves
`load_config(repo).fingerprint_ignore`. No second definition, no per-caller
override. Evidence: `src/loop_harness/stamp.py:61`. UPHELD.

### Whole-tree code guarantee (MANIFESTO §1; stamp.py:8-10; ticket §6)
Still subtract-only: `git rm -r --cached --ignore-unmatch -q -- <pattern>`
at `src/loop_harness/stamp.py:111-114`. The new empty-pattern check
tightens, never loosens. `all()` over an empty list is `True`, so an
absent/`[]` key still yields `()` and today's whole-tree behavior; only
non-empty patterns subtract. Evidence: `src/loop_harness/config.py:229-241`.
UPHELD.

### I8 / fail-safe direction (MANIFESTO §1:30-32; §3:138-142)
A policy ambiguity (broken config) must fail SAFE toward more hashing,
never toward less. The new empty-pattern check raises `ConfigError`
(`config.py:235-240`), which `load_config` re-raises unchanged
(`config.py:266-267`), and `fingerprint_ignore_failsafe`
(`hooks.py:204-215`) catches to return `()` — the strictest whole-tree
list. This is the correct direction and closes a real fail-open hole: the
commit-gate body fails OPEN on exceptions (`hooks.py:242`), so an empty
pathspec that made `git rm` fatal inside `tree_fingerprint` would have
silently disabled the gate; rejecting it at load time routes the broken
config to the SAFE strict list instead. Defense in depth aligned with the
deliberate I8 / fail-open split (MANIFESTO:200-203). UPHELD.

### Surgical scope (MANIFESTO §4 value:204-206; ticket §6)
Every changed line traces to the ticket surface. Follow-up 1 is a ~6-line
validation block plus one test; follow-up 2 is docstring text and one README
block. No adjacent refactors, no unrelated edits. UPHELD.

### Tests and docstrings ship with the code (MANIFESTO §4 value:209-211)
The empty-pattern behavior is pinned by
`test_empty_fingerprint_ignore_pattern_raises`
(`tests/test_config.py`, `match="empty pattern"`, covers whitespace-only).
The `tree_fingerprint`, `write_stamp`, `verify_stamp`, and
`LoopConfig.fingerprint_ignore` docstrings document git-pathspec semantics
and the over-broad-shadowing danger, matching the ticket §6 obligation.
UPHELD.

## README consistency

The `README.md` `fingerprint_ignore` section states the same three facts the
docstrings now state: git-pathspec (not `.gitignore`) semantics with the
`*.lock` / `aim.lock.toml` example, the subtract-only direction, and the
over-broad `.`/`src` shadowing danger, plus "An empty pattern is rejected."
Consistent with `LoopConfig.fingerprint_ignore` and `tree_fingerprint`
docstrings and with the config error message.

The corrected `tree_fingerprint` docstring no longer makes the earlier
absolute "real code can never commit ungated" claim; it now scopes the
guarantee to non-ignored paths and names honest patterns as the operator's
responsibility. This removes a prior overclaim rather than introducing one,
which strengthens rather than erodes the whole-tree framing.

## Where the baseline is silent
- The Manifesto does not constrain README structure or config-validation
  message wording; no rule asserted there.
- `stamp.py` importing `load_config` for `stamp.main` (unchanged from the
  prior round) introduces no external dependency and no import cycle
  (`config.py` does not import `stamp.py`), so the dependency-free-core
  value (MANIFESTO:197-199) is intact.

## Verdict

No architectural invariant is disturbed by the follow-ups. They strengthen
the fail-safe posture and keep the docs consistent with the code. PASS,
bound to tree f07318510134bcbf3f5b0d8bee9bba9c24528de3. The commit gate must
reject any commit whose tree differs.
