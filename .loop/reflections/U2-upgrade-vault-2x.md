---
slug: U2-upgrade-vault-2x
blockers: [out-of-scope-fix-needed]
friction: [other:out-of-band-implementation]
worked: [other:wildcard-question-settled-empirically]
harness_change: closing a ticket implemented outside the loop (no worktree, no stamp) needs a lighter path than redoing the full lifecycle for a zero-diff pickup
---

## What worked

Open Question 2 (whether Vault 2.0.1's wildcard rejection breaks the
identity-templated `nomad-workloads` policy) was the one thing that could
have blocked this ticket, and it was settled empirically before the manager
was touched: an isolated `vault server -dev` on 2.0.3 with a JWT mount
mirroring `jwt-nomad` showed the wildcard ALLOWED. Vault 1.21.4-1 was
upgraded to 2.0.3-1 on the manager, confirmed unsealed on Consul storage,
`jwt-nomad` intact on the same accessor, and a live workload (`grafana`)
proving it could still render its Vault-backed template after the restart.

## What worked less well

This ticket was implemented and merged (`547cab0`, 2026-07-31) outside the
normal loop ceremony: no worktree, no `loopctl stamp`, no review pass, and
the commit subject did not carry the ticket slug, so the harness never saw
it. A later commit (`b408189`) archived this ticket's plan/eval files before
the ledger ever advanced, leaving it `blocked` against a stale "restore the
staged files" remedy that no longer applied once that commit landed. The
plan's own R3 (rehearse the restore on an isolated instance before touching
the manager) was not met: the apply went ahead on the cached
`vault_1.21.4-1_amd64.deb` and Consul snapshots alone, which the plan itself
flags as the main gap. Closed out retroactively: unblocked to `ready`, wrote
this reflection, and let `loopctl reconcile` recognize the closing commit
and advance the ledger to `done`.
