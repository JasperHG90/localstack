---
slug: R9-rollout-tempo-keyless-minio
blockers: []
friction: [other:proxy-accepted-too-early, other:fix-introduced-regression, other:eval-assumed-unavailable-access, other:review-cap-pressure]
worked: [premise-verified-at-source, real-measurement-over-proxy, reviewer-supplied-route]
harness_change: eval-amend refuses an amendment that drops a symbol the PLAN still backticks, so retargeting a row means editing the plan first. That coupling is correct but undocumented, and cost two failed amendments across two tickets.
cycles: 3
gates_red: 0
---

## What worked

**Verifying the premise at source before writing the ticket.** The whole
plan rested on tempo reaching minio-go's IAM provider with a settable STS
endpoint. Reading `s3.go` and `iam_aws.go` at the pinned tags turned that
from a hope into a citation, and the plan reviewer then confirmed it by
running the real image against a wire logger. Nothing in the mechanism
needed a second attempt, across three review cycles. The cost of an hour
reading upstream source bought a change that worked the first time it was
applied.

**Refusing to let a proxy stand when a measurement was reachable.** Both
weakened eval rows became real measurements: one OTLP span produced four
observed PUTs, and a throwaway user bound only to the `tempo` policy proved
MinIO enforces it. Neither was expensive. The first cost one SSH command
and a 30-minute wait; the second cost four commands and a delete.

**Reading the whole reviewer verdict, not just its severity.** Twice a
finding carried its own better fix. M1's reviewer established that MinIO
does not validate role-policy existence at load, which turned "delete the
target" into "point it at a policy that does not exist". Here the reviewer
quoted the plan-review transcript showing the PUT route I had written off.

## What worked less well

**I accepted two proxies before proving the door was shut.** I wrote that
the write path was "unscoreable" when it was unscoreable PASSIVELY: pushing
a span was one SSH command away, and this ticket's OWN plan review had
already demonstrated the route and written it down. I had read that verdict
and still missed it. Worse, "unscoreable" closes a door for the next
reader, who has no reason to re-test it. The same error shape appeared in
the second row, where "cannot be extracted by any route" was a universal
claim built from one API's refusal.

The lesson is narrower than "test more": when writing that something cannot
be measured, the sentence needs the same evidence standard as a claim that
something works. I applied that standard to the mechanism and not to my own
excuse.

**A fix I made turned a stale sentence into a false one.** The doc said "no
existing consumer was moved off them", which had merely gone stale. I
replaced it with a named list, "loki and registry still use theirs", which
is a stronger claim and wrong, because memex is still keyed. Tightening
vague prose into an enumeration is exactly where a stale sentence becomes a
false one, and the audience for that line is whoever audits which services
still hold static keys.

**The eval assumed access the cluster does not grant.** Two rows were
written against `nomad alloc exec` and against reading the JWT out of
`secrets/`. Nomad refuses both: the image is distroless and `alloc fs` will
not read secrets. Both were discovered during implementation, not planning,
because the plan reasoned about what the mechanism does rather than about
what the operator can observe. An eval row should be checked for
executability at authoring time, the way a gate command is.

**The review cap shaped the last cycle.** Cycle 3 of 3 arrived with four
non-blocking advisories outstanding, including a genuinely correct one
(minio-go also honors two deprecated `AWS_*` aliases, so the absent-name
list is eight, not six). Fixing them would have needed a fourth cycle and
blocked the ticket. Correct under the rules, but it means the cap converts
late small findings into follow-ups rather than fixes.

## Follow-ups

- The credential-name list in `docs/workload-identity.md` says six names;
  `env_aws.go` also honors the deprecated `AWS_ACCESS_KEY`/`AWS_SECRET_KEY`
  aliases, making it eight. Nothing in the tree sets either.
- Related: the doc says leaving a name set keeps the service on its old key.
  `chain.go` advances only when key AND secret are both empty, so a lone
  `AWS_ACCESS_KEY_ID` sends the client anonymous instead.
- Claim mode keys on `nomad_job_id` alone, so a job of the same name in
  another Nomad namespace would match this policy. M1's mechanism and this
  ticket's non-goal 3, but worth its own ticket before R10 and R11 widen
  claim mode to logs and images.
- The synthetic trace pushed to score the write path
  (`service.name=r9-keyless-eval`) stays in the tempo bucket until it ages
  out under the existing 30-day retention.
- Tempo's static key, its MinIO user and its Vault KV entry are kept as the
  rollback path. Remove them once this has held.
