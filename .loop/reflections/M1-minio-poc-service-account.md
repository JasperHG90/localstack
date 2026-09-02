---
slug: M1-minio-poc-service-account
blockers: []
friction: [other:stale-block-reason, other:worktree-tfvars-gap, other:reviewer-api-death, other:throwaway-privilege-pin]
worked: [two-phase-proof, live-eval-evidence, reviewer-supplied-fix]
harness_change: preflight-artifacts could also check whether a ticket's block reason still cites the current verdict, since M1 sat blocked on a superseded one.
cycles: 3
gates_red: 0
---

## What worked

**The two-phase proof earned its cost.** Wiring `role_policy` first, before
claim mode, meant the first STS call tested exactly one thing: does MinIO
trust Nomad at all. When it returned credentials, everything after it was
about RBAC, not trust. Had both changed at once, a failure would have had
two candidate causes and no way to separate them.

**Recorded live evidence survived teardown.** The POC job and policy were
destroyed before review, so the reviewer could not re-run the read legs. It
still scored the claim-mode row, because the saved STS response was itself
proof: the session token carries no `roleArn`, and MinIO cannot mint that
credential unless a policy named `m1-poc` existed at that instant. Keeping
the raw artifact was worth more than a transcript of the command.

**A reviewer finding carried its own fix.** The adversarial pass found POC2
granting `s3:*` on the memex bucket to anyone naming its audience. I was
about to delete the target. The same verdict established that MinIO does not
validate role-policy existence at config load and checks per request, which
made a deliberately undefined policy name the better fix: the multi-IdP
shape survives and the grant disappears. Reading the whole verdict, not just
its severity, changed the outcome.

## What worked less well

**The ticket was blocked on a verdict that no longer existed.** M1's ledger
entry cited a premise as BROKEN, but the current plan-validator verdict on
disk said SOUND, and both required fixes were already applied. The block
outlived its cause and nothing noticed. Cheap to check, expensive to leave:
this ticket was pickup-ready for some time.

**`just worktree_setup` copied one root's tfvars, not both.** The
applications root's `prod.tfvars` is gitignored and was never copied, so
`terraform plan` fails in any fresh worktree. The gate never caught it
because `terraform validate` does not read tfvars, so this only bites the
apply, which is exactly where it is most annoying. Fixed here.

**A reviewer died mid-write and left a placeholder.** The cycle-1
adversarial pass hit an API error while writing its verdict. The fail-first
placeholder meant the commit gate stayed shut rather than defaulting open,
which is the design working, but the cycle was lost and had to be re-run
from scratch.

**I put a standing grant on shared infrastructure to satisfy a sentence.**
POC2 needed a `role_policy` because only one target may run in claim mode,
and I reached for a real policy name that happened to be handy. That handed
`s3:*` on a live bucket to any future jobspec author who typed the matching
audience. The lesson generalizes past this ticket: on a throwaway component,
the throwaway-looking field is the one to check hardest, because nobody
audits what they read as scaffolding.

## Follow-ups

- Doc nit D12/A2, non-blocking: the quoted error is
  `None of the given policies are defined`, but MinIO interpolates the
  policy name, so a literal log grep misses. Two-word fix.
- Advisory A1: the fail-closed property behind POC2 holds only while no
  external authorization plugin is configured. Neither the jobspec comment
  nor the doc says so.
- No service is keyless yet. The first real consumer needs a policy named
  for its job id; loki, tempo and registry each depend on whether their S3
  client can do web identity against a non-AWS STS endpoint, which is
  unverified per service and looks blocked upstream for loki
  (grafana/loki#8014 is open).
