---
slug: stamp-fingerprint-ignore-list
cycles: 1
gates_red: 0
blockers: []
friction: [other:adversarial-found-real-security-gaps]
worked: [eval-as-spec-concrete-dod, tests-first-caught-signature-drift, reviewers-agreed]
harness_change: Consider a cheap static guard rejecting the three degenerate whole-tree fingerprint_ignore patterns (".", "*", "**") as defense-in-depth alongside the documentation route.
---

## What worked

The eval's seven rows drove the design directly: the guarantee-preserving
row became the first test written, and writing tests first surfaced the
five-caller signature drift immediately (every un-threaded call site was a
red test, not a runtime surprise). Both review passes agreed the
single-definition invariant held, and the caller-drift grep audit gave a
mechanical check that no site was missed. The Q1-recommended shape
(explicit `ignore` arg resolved by the caller, config never read inside
the fingerprint) kept a `ConfigError` out of the hot path and let the hook
apply its own strict-fallback failsafe.

## What worked less well

The first adversarial pass found two real security gaps the deterministic
tests did not: an empty pattern (`""`) passed validation but made
`git rm -- ""` fatal, which the commit hook's fail-open would swallow and
silently disable the gate; and the `tree_fingerprint` docstring over-claimed
"real code can never commit ungated," which is false under an over-broad
pattern like `.` or `src` that shadows source. Both were legitimate and
cost one review cycle to fix (validation rejects empty patterns; docstrings
and the README now document the git-pathspec shadowing danger). Tagged
`other:adversarial-found-real-security-gaps`: the adversarial pass earned
its keep here on a security-critical invariant, exactly where the harness
is meant to catch what the implementer's own tests miss. The residual
over-broad-pattern risk (`.`, `*`, `src`) is handled by documentation, not
static rejection, because a complete denylist is impossible; the
harness_change above notes a cheap partial guard as a candidate follow-up.
