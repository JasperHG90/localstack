---
type: verdict
title: 'Verdict: docs-howto plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of docs-howto: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T17:54:07+00:00'
slug: docs-howto
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Pass. The spikes settle all three listed risks, the repo claims the plan rests on check out, and each eval row's command checks exactly its fails_when.

## Checked

- Risk 1 (kmctl sections), spike:docs-reconcile/3: the script added front matter to `docs/how-to/log-in-to-vault.md`, ran `check --fix` and `check`, got exit 0 and no section finding. It also showed that a real `sources` path (`justfile`) gives no notice and a missing one gives a `source not resolved` notice. That is the case r2 relies on.
- Risk 2 (pages that belong in .okf), spike:docs-reconcile/1: 0 of 81 pages. Its 11 build-history pages are covered by r5.
- Risk 3 (code bugs), spike:docs-reconcile/2: 0 of the path and recipe drift is a code bug. The plan states the prose-claim limit and sends prose-claim bugs to step 8.

Claims checked against the repo:
- 51 how-to pages plus README.md, and no subdirectories, so `glob("*.md")` in r1 and r4 covers them all.
- `test_how_to_skeleton.py` reads headings only, so YAML front matter does not trip it. `test_docs_index.py` needs every page linked from `docs/README.md`, which step 5 covers. The doc-drift checks in `test_backup_coverage.py` read only `docs/reference/gcs-backups.md`, so this ticket does not touch them.
- `kmctl review due --json` has a `notices` list whose entries carry `path` and `message`, which matches r2. `kmctl check` prints warnings as `warning  <kind>  <path>`, which matches r3's `^warning` grep. Today `kmctl check` passes with one warning, on `.okf/summary.md`.
- `docs/note-sync.toml` is tracked. `docs/notes/` is untracked and holds an empty `main/` directory, so deleting it needs `rm -r`. Nothing in the justfile or `cli/` reads note-sync. The only other mention is history in `.okf/practices/plan-premise-sweep.md`.

Eval rows: each command checks exactly its fails_when.
- r1 also catches a page with no front matter (an empty dict counts as bad).
- r2 is stricter than the outcome: it fails on any notice, not only `source not resolved`. That is fine.
- r4 run on HEAD flags 26 shorthand tokens. Spot-checked, none is a runtime or other-codebase name colliding with a tracked file (`bifrost_smoke.py` is `scripts/bifrost_smoke.py`). r4 is narrower than the outcome's "every backticked repo path resolves", because it misses tokens without an extension and dead full paths. Its fails_when says so honestly, and r5 covers the rest.
- r6 is exact.

## Findings

None.

## Notes

Not blocking:
- `docs/.gitignore` ignores only `.memex-sync.db`, so it goes stale once note sync is dropped. The implementer should remove it with step 7.
- Step 6 relays to `okf-reconcile`, which will already be done because this ticket depends on it. With 0 pages found, that path should not trigger.
