---
slug: U3-upgrade-nomad-2x
blockers: [out-of-scope-fix-needed]
friction: [other:out-of-band-implementation]
worked: [other:advertise-fix-landed-before-restart]
harness_change: closing a ticket implemented outside the loop (no worktree, no stamp) needs a lighter path than redoing the full lifecycle for a zero-diff pickup
---

## What worked

Nomad went from 1.11.3-1 to 2.0.4-1 on all five nodes, server first then
each client in turn, verified before moving to the next. The advertise-block
fix (`c744b92`) was applied to every client before its restart, which
mattered directly: a restart with no advertise block and `bind_addr =
"0.0.0.0"` is exactly what advertised the podman bridge and took four of
five nodes down during the incident this epic responded to. Doing the
upgrade without that fix first would have reproduced the same outage and
mis-attributed it to the version bump. Verified after: all five agents
`2.0.4 ready`, 19 jobs running, correct advertised addresses, and the
podman driver (still 0.6.4-1) loading fine under 2.0.4.

## What worked less well

This ticket was implemented and merged (`547cab0`, 2026-07-31) outside the
normal loop ceremony: no worktree, no `loopctl stamp`, no review pass, and
the commit subject did not carry the ticket slug, so the harness never saw
it. A later commit (`b408189`) archived this ticket's plan/eval files before
the ledger ever advanced, leaving it `blocked` against a stale "restore the
staged files" remedy that no longer applied once that commit landed. Closed
out retroactively: unblocked to `ready`, wrote this reflection, and let
`loopctl reconcile` recognize the closing commit and advance the ledger to
`done`. No code changed here; the upgrade was already correct on disk and
on the cluster.
