---
slug: fingerprint-binds-loop-config
cycles: 0
gates_red: 0
blockers: []
friction: [compound-stamp-commit, prek-first-pass-rewrite]
worked: [tests-first-reproducer]
harness_change: implement-ticket step 6 should tell the driver to use a bare `git commit` (no `&&`/pipe/redirect), so the target-repo commit gate does not fail-safe block it
---

## What worked

Writing the two binding reproducers first and confirming they FAILED on the
pre-fix code made the fix unambiguous. The adversarial reviewer independently
loaded HEAD's pre-fix `tree_fingerprint` and confirmed the reproducers are
non-tautological. Binding the whole `config.json` after the ignore loop (R4)
was a small, single-sourced change every caller inherited, and both review
passes passed on the first cycle.

## What worked less well

The commit gate (from `commit-gate-targets-the-committed-repo`) fail-safe
blocked `git add -A && git commit ... | tail`: it could not resolve the target
repo from a compound, piped command. Splitting into a bare `git add` then a
bare `git commit -F <file>` cleared it, but the failure mode is non-obvious
from the message. `prek` also reformatted `test_stamp.py` on its first pass,
costing a re-run before the stamp landed.
