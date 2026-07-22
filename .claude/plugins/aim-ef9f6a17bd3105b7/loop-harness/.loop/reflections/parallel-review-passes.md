---
slug: parallel-review-passes
cycles: 0
gates_red: 0
blockers: []
friction: [other:subagent-registry-stale]
worked: [dogfooded-the-change, driver-only-scope]
harness_change: register newly-added review-pass agents without a session restart, or fail the enabling config loudly when the agent is undispatchable
---

## What worked

The change was driver-only, so the scope stayed to one file
(`skills/implement-ticket/SKILL.md`); the ticket's own claim "no harness
code needed" held under review because the commit gate already iterates
enabled passes as a set and checks each verdict is tree-bound, regardless
of dispatch order. The review itself dogfooded the change: with two passes
now enabled (adversarial + architectural), both were dispatched
concurrently against one shared fingerprint captured from
`.loop/stamp.json`, exactly as the rewritten step 5 prescribes, and both
bound cleanly to the same tree.

## What worked less well

`other:subagent-registry-stale`: the `.loop/config.json` change (committed
just before this ticket) enabled the `architectural` pass whose agent is
`loop-harness:loop-architect`, but that agent type was not in the session's
dispatchable registry even though `agents/loop-architect.md` exists and is
declared in the plugin manifest. The concurrent dispatch of the two passes
half-failed: the adversarial pass ran and passed, the architectural pass
errored with "agent type not found". A session restart reloaded the
registry and the architectural pass then ran and passed against the same
(still-stable) tree, so no re-stamp was needed. The failure mode to fix:
enabling a review pass whose agent is undispatchable should fail loudly at
config-load or at review dispatch, not half-succeed at review time.
