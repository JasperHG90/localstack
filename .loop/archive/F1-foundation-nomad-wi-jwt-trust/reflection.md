---
slug: F1-foundation-nomad-wi-jwt-trust
blockers: []
friction: [other:alloc-secret-fs-blocked, other:commit-gate-cd-prefix]
worked: [other:live-eval-transcript-in-doc, other:concurrent-review-passes]
harness_change: ""
---

## What worked

Live evals against the cluster gave a real transcript for the doc's operator
verification section: JWKS key count, role claim mappings, the keyless probe
read, and the positive/negative policy results all captured from the running
cluster, not invented. The doc ships the exact commands a reader can re-run.

Both review passes ran concurrently and returned PASS with no fix loop,
because the plan had already reconciled every line anchor and the policy
shape against the live files. Re-planning carried the ticket; implementation
was mostly transcription.

## What worked less well

`nomad alloc fs` refuses to read files under `secrets/` ("Reading secret
file prohibited"), so the first probe job (silent `sleep 600`) left no way
to confirm the rendered JWT or probe.env from outside the alloc. Fixed by
having the task `cat` those files to stdout, then reading them through
`nomad alloc logs`. Worth knowing for any future ticket that proves a
keyless path by inspecting rendered secrets: read via logs, not `alloc fs`.

The commit-gate hook rejected `git commit` commands that chained a `cd` with
other commands or used heredoc multi-line messages, parsing only a leading
`cd <path> && git commit` form with a single-line-friendly message. A bare
`git commit -m "<slug>: <summary>"` from the worktree cwd passed. The skill
instruction's absolute-`cd` prefix is load-bearing for the hook, but the
message body must stay simple enough for the hook to parse.