---
slug: U1-upgrade-pin-hashistack-versions
blockers: [out-of-scope-fix-needed]
friction: [other:out-of-band-implementation]
worked: [other:apt-pin-verified-live]
harness_change: closing a ticket implemented outside the loop (no worktree, no stamp) needs a lighter path than redoing the full lifecycle for a zero-diff pickup
---

## What worked

The version pins landed in `bootstrap/inventory/group_vars/all.yml` and the
apt-preferences ordering fix in `bootstrap/playbooks/install_dependencies.yml`
were verified live rather than asserted: `apt-get -s dist-upgrade` offered
`nomad-driver-podman 0.6.5-1` before the pin and nothing after it, on every
node. Commit `547cab0` carries the actual change.

## What worked less well

This ticket was implemented and merged (`547cab0`, 2026-07-31) outside the
normal loop ceremony: no worktree, no `loopctl stamp`, no review pass, and
the commit subject did not carry the ticket slug, so the harness never saw
it. A later commit (`b408189`) archived this ticket's plan/eval files before
the ledger ever advanced, leaving it `blocked` with `out-of-scope-fix-needed`
against a stale "restore the staged files" remedy that no longer applied
once that commit landed. Closed out retroactively: unblocked to `ready`,
wrote this reflection, and let `loopctl reconcile` recognize this closing
commit and advance the ledger to `done`. No code changed here; the pin and
the upgrade were already correct on disk and on the cluster.
