---
slug: R13-rollout-loki-registry-keyless-minio
blockers: []
friction: [other:scope-dropped-when-tightening-prose, other:fix-reported-unverified, other:double-template-escaping, other:absence-mistaken-for-evidence, other:fix-left-siblings-stale]
worked: [one-mechanism-two-consumers, probe-before-planning, fail-loud-helper, positive-evidence-over-clean-scan]
harness_change: A plan-review correction that rewords a claim does not propagate to prose written later from the same understanding. The image-pin error was fixed in the plan and then reintroduced verbatim in the doc.
cycles: 3
gates_red: 0
---

## What worked

**Probing the containers before writing the plan.** Three facts decided the
whole design, and all three were one command away: both images ship a shell,
both ship `wget`, both run as root. Had any been false the ticket would have
needed a sidecar or an image rebuild. Checking first turned a Medium ticket
with an unknown into a Small one with none.

**One mechanism for two consumers, chosen against the earlier plan.** R10 and
R11 assumed two different routes, and R10's carried a real risk: switching
loki to thanos objstore would have swapped its entire storage client and put
existing log data in question. `credential_process` serves both services and
leaves both storage clients alone. The two tickets collapsed into one that is
smaller than either.

**The helper fails loudly by construction.** It exits non-zero rather than
emitting a half-document, and that guard caught the escaping bug on its first
run with a message naming the problem. Had it printed JSON with empty fields,
the SDK would have reported its own error and the actual cause would have
been two layers down. The reviewer later found the better reason for that
same guard: with no `Expiration`, `processcreds` sets `staticCreds = true`
and the SDK never re-runs the helper, so the credential silently stops
working after an hour.

**Chasing positive evidence instead of a clean scan.** For the refresh
question I looked for writes after the expiry boundary rather than an absence
of errors. That was the right instinct and the reviewer confirmed why:
registry's log ran silent for twelve minutes across the boundary, so a clean
error scan would only have proved it was idle.

## What worked less well

**I dropped a scope qualifier while tightening prose, for the third time in
two tickets.** "memex is the only MinIO consumer still using one" replaced a
sentence scoped by "theirs" to four jobs. `backup-minio` runs on the root
credential and `storage.tf` mints keys nothing consumes, so the rewrite was
false. R9 had the same shape twice: an enumeration that dropped memex, and a
count that said six names where the plan required more. The pattern is
specific and worth naming: turning a vague-but-scoped sentence into a
specific one is where a stale claim becomes a wrong one, and the specificity
is what makes a reader trust it.

**I reported a fix as done without checking the line it lives on.** I told the
reviewer the "the two are opposites" clause was dropped. My edit matched a
similar sentence elsewhere; the real text was "the two symptoms are
opposites" and was never touched. `git diff | grep opposites` would have
caught it in a second. Claiming a fix landed is a factual claim about the
tree and needs the same evidence as any other.

**Double-template escaping cost a deploy cycle.** The helper is shell
rendered through Terraform's `templatefile` and then Nomad's template engine.
I wrote `$$1` for a shell positional, reasoning from `$${` which Terraform
does escape. Terraform only treats `${` specially, so `$$1` reached the shell
as PID-then-1 and every sed match came back empty. Rule: escape `${`, leave
every other `$` alone, and read the rendered artifact rather than the source
before believing it works.

**Fixing prose in one place left the same claim wrong next door.** The doc's
"must match exactly" became "differ by a leading slash", and both jobspec
comments kept saying "must stay identical". Followed literally the stale
version is a small trap, since an absolute `destination` is rejected. A fix
should sweep for its own wording, not just its own file.

## Follow-ups

- `loki.hcl` and `registry.hcl` still say the helper path and
  `AWS_CONFIG_FILE` "must stay identical". They differ by a leading slash.
  One line each; the plan's own wording is the root.
- `docs/workload-identity.md` still says "the two symptoms are opposites"
  over a passage describing three, two of which are loud. End the sentence
  at "depends on how you reach MinIO".
- The doc explains the helper's empty-field guard as protecting against blank
  credentials. The stronger reason is the missing `Expiration` disabling
  refresh outright.
- Both static keys stay provisioned as rollback paths. Removing them, and
  their MinIO users and Vault entries, is the change that actually reduces
  the credential surface. Worth its own ticket once this has held.
- memex is the only one of the four still keyed, dropped by the operator
  because its fix needs application changes in another repo.
