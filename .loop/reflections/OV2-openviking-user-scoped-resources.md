---
slug: OV2-openviking-user-scoped-resources
blockers: []
friction: [other:wrong-checkout-edits, other:plan-bound-before-last-edit, other:premise-invented-not-probed]
worked: [other:probe-before-plan, other:reviewer-executed-the-runbook]
harness_change:
---

## What worked

**Probing the dependency instead of reading it.** Every load-bearing claim was
run against the deployed version (`uv run --with "openviking==0.4.17.1"`)
rather than inferred: `is_accessible` in both directions, `~` resolution per
caller, `ServerConfig` accepting the config shape, and the Terraform key
derivation compared to the server's own `generate_api_key`. Two of those
probes changed the design. The access probe is what proved the isolation, and
the key probe is what turned "no secret should rotate" from a hope into a
checked fact.

**Reviewers that execute rather than read.** The adversarial pass rendered the
provisioner's six-deep escaping into a real `/bin/sh` script with a `curl`
shim, and later executed the docs runbook the same way. That caught what
reading would not have: the re-mint endpoint returns the NEW key unconditionally,
so the runbook as written would have replaced two leaked keys with two fresh
ones in the operator's scrollback. A prose review passes that.

## What worked less well

**Edits landed in the primary checkout, not the worktree.** The Bash tool
resets cwd between calls, and every edit used a repo-relative path. The
Terraform edits happened to land in the worktree; the whole docs rewrite landed
in the primary checkout on `main`. Caught only because `git diff --stat` came
back empty in the worktree. Both checkouts sat at the same HEAD, so moving the
file across and restoring the primary was clean — it would not have been if
`main` had moved. Use absolute paths under the worktree root, or verify `pwd`
in the same call that edits.

**The eval was bound to the plan before the plan stopped moving.** The skill
says bind LAST; the binding went in, then two spelling fixes and an §8
paragraph followed. Both review cycles reported it as a plan-drift advisory
that only an operator can clear, from the primary checkout, with a
counter-signer. Cheap to avoid, annoying to undo.

**Two premises were invented rather than probed, and both were symbol names.**
`_uri_to_agfs_path` and `_request_user_deletion` do not exist in 0.4.17.1; the
real names are `_uri_to_path` and `begin_user_deletion`. Each was caught by a
different planning cycle, and the second one after the first had already been
flagged. A `path:line` anchor proves a file exists, not that the symbol in the
sentence does. Quote symbol names from `grep`, never from memory.

**Four planning cycles, and the first two earned their keep.** Cycle 1 killed
the original design (a config default that Studio and WebDAV both bypass).
Cycle 2 inverted the cost story: the old account is not stranded, its keys are
never revoked. Cycle 3 found that per-user offboarding cannot work under one
account per person. Cycle 4 found only stale anchors. The rule that emerged:
stop when a cycle returns no design defect, and hand the operator the residual
rather than spending another pass on cosmetics.
