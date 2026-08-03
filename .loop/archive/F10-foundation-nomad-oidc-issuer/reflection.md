---
slug: F10-foundation-nomad-oidc-issuer
blockers: []
friction: [other:comment-nit-forced-full-restamp, other:relay-finding-mid-loop]
worked: [other:one-line-code-surface, other:plan-carried-forks]
harness_change: ""
---

## What worked

The plan carried every fork to a settled resolution before pickup, so
implementation was one template line plus one playbook variable. Q1's
issuer URL was settled by live evidence (the edge already routes
nomad.lab.orangecluster.nl over HTTPS), not by the implementer. The
eval marker was signed ahead of time, so the require_eval gate cleared
on the first advance.

Relay-finding ran mid-loop without disturbing the source ticket's stage:
the M1 plan edit landed and the source kept its scope. Subticket 1
(relay FIRST) prevented two tickets both believing they own
oidc_issuer.

## What worked less well

A single non-blocking comment-nit from the adversarial pass (the
template comment loosely said F1's doc "points M1 at this URL" when F1
defers discovery to F10) forced a full re-stamp and a re-run of BOTH
review passes against a new tree, because the commit gate needs every
verdict bound to the same tree. The fix was a two-line comment reword;
the cost was two more reviewer dispatches. A verdict that recorded
which paths it examined could re-bind when its own scope did not move,
same finding as F14-role-taxonomy's and G2's reflections, now with a
third ticket's evidence. Non-blocking findings that touch only
excluded-from-fingerprint prose (a comment) staling a tree-bound
verdict is the sharpest instance yet.