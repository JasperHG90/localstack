---
slug: U4-upgrade-consul-2x
blockers: [out-of-scope-fix-needed]
friction: [other:out-of-band-implementation]
worked: [other:vault-survived-consul-restart]
harness_change: closing a ticket implemented outside the loop (no worktree, no stamp) needs a lighter path than redoing the full lifecycle for a zero-diff pickup
---

## What worked

Consul went from 1.22.6-1 to 2.0.2-1 on all five nodes, server first. The
open question that mattered most (whether Vault seals when Consul restarts
under it) resolved cleanly: Vault logged zero errors and zero seal events
during the server restart and stayed unsealed throughout, leader back in
about ten seconds. Snapshots were taken before, and again after the Nomad
and Vault upgrades, and again after verification, since a snapshot only
restores into the version that took it. Every client checked its apt cache
showed the 2.0.2-1 candidate before installing, so a stale cache could not
produce a silent no-op. Verified after: all five members alive, all 25
services present, `vault/` and `terraform/` KV prefixes intact, and a clean
`terraform plan` (no changes) in both roots, which is the check that
actually proves state survived, not just the presence of the keys.

## What worked less well

This ticket was implemented and merged (`547cab0`, 2026-07-31) outside the
normal loop ceremony: no worktree, no `loopctl stamp`, no review pass, and
the commit subject did not carry the ticket slug, so the harness never saw
it. A later commit (`b408189`) archived this ticket's plan/eval files before
the ledger ever advanced, leaving it `blocked` against a stale "restore the
staged files" remedy that no longer applied once that commit landed. No
restore rehearsal into a scratch 1.22.6 instance was done; the snapshots
were verified only with `consul snapshot inspect`, which the plan itself
flags as weaker than an actual restore and the main gap in this apply.
Closed out retroactively: unblocked to `ready`, wrote this reflection, and
let `loopctl reconcile` recognize the closing commit and advance the ledger
to `done`.
