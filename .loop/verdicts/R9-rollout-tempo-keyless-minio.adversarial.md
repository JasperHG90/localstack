---
verdict: pass
tree: 0c6778a949abcb3d91b425d94ce64fa5585acd23
---

# Adversarial review, cycle 3 (final) — R9-rollout-tempo-keyless-minio

**Verdict: pass.** Nothing blocks. Commit it.

## Binding

This verdict declares NO `bound_paths:` / `scope:` / `citations:`, so it
falls back to whole-tree binding, which is stricter than any path set I
could name. My briefing carried a tree fingerprint and no 64-hex scope
digest, and a digest the reviewer computes is compared at commit time
against a value recomputed the same way, so it binds nothing. Recording one
would have been ceremony. My cycle-1 and cycle-2 verdicts omitted these
lines for the same reason.

The tree fingerprint I was briefed with is the one I reviewed: `git diff
--stat 0c6778a949ab... -- . ':(exclude).loop'` is empty.

The path set I was shown, for the human reader (this is prose, not a
binding). The repo's `.loop/config.json` declares no
`verdict_binding_inputs`, so `.loop/` is stripped from the certified-tree
universe and these four are the complete set of changes the commit gate can
see:

- `deployments/applications/services.tf`
- `deployments/applications/services/tempo.hcl`
- `deployments/applications/storage.tf`
- `docs/workload-identity.md`

The anchors I cite below all sit inside those four files:
`docs/workload-identity.md:267,269,373-379,382-385`,
`deployments/applications/storage.tf:100-102`,
`deployments/applications/services/tempo.hcl:60,61,73,94,96`, and
`deployments/applications/services.tf:254`.

## Deterministic floor

`loopctl verify-eval-substance R9-rollout-tempo-keyless-minio` prints
`valid`. No hard-fail, no `warn:` advisory, so no plan-drift reading
instruction to discharge. Proceeded to the semantic pass.

## Gate, re-run independently

The cycle-2 trust stamp is keyed on `180263895eba...`, which is not this
cycle's fingerprint, so the stamp does not apply and I re-ran the gate
rather than trusting it. `just pre_commit` from the worktree root: all 18
hooks pass, exit 0. Re-stamped at
`.loop/scratch/R9-rollout-tempo-keyless-minio.adversarial/trust-stamp.json`
for `0c6778a9...`.

What the gate does NOT cover, per `.pre-commit-config.yaml`: it formats and
validates HCL and Terraform and runs Python lint/type/test for `cli/` and
the dash backend. It reads no prose and no comment. Every claim in
`docs/workload-identity.md` and every comment in the three infra files is
therefore unexercised by the gate, and the eval covers only E1-E6. That is
where I spent this pass.

## What changed since the tree I passed

`git diff 180263895eba... 0c6778a949ab...` is exactly the three files and
the edits the briefing described: comment rewraps in `tempo.hcl`, the B1
wording fix in `storage.tf`, and four prose edits in the doc. No Terraform
resource, jobspec value, env var, policy or identity block moved. I
confirmed that against the diff rather than taking it on the hand-off.

## Live re-verification (the ticket's substance, re-attacked not inherited)

Cluster reads via `localstack env` + a brokered Nomad token. Nothing was
written to the repo tree; scratch stayed under
`.loop/scratch/R9-rollout-tempo-keyless-minio.adversarial/`.

- `nomad job inspect tempo` (version 2, running): `Env` is exactly
  `{TEST_IAM_ENDPOINT, AWS_WEB_IDENTITY_TOKEN_FILE}`, `Vault` is `None`,
  one `Identities` entry with `Audience: ["minio"]`, `File: true`,
  `Filepath: secrets/nomad_minio.jwt`, `TTL 3600s`, `ChangeMode noop`, and
  one template with `Envvars: false`. Matches the reviewed jobspec
  field for field.
- Grepping that jobspec for all EIGHT credential names (the doc's six plus
  the two legacy AWS names) and for `AWS_ROLE_ARN` returns zero matches
  each.
- E1: `nomad alloc fs 0240b708 tempo/secrets/` lists `nomad_minio.jwt`, no
  `minio.env`. Reading the JWT is still refused: `Reading secret file
  prohibited`, with a management token (A2 holds).
- E3a/E3b: the current alloc PUT `single-tenant/index.json.gz` and
  `index.pb.zst` at 23:52:55 CEST, matching its own `poller.go:302`
  `writing tenant index` line at 21:52:55.159Z; the four block objects from
  21:31:58Z persist. Anonymous list on the bucket is HTTP 403. With two env
  vars and no Vault, those PUTs could only be STS-signed.
- Zero `Access Denied` / `AUTH: None` / `SignatureDoesNotMatch` across the
  whole alloc log, 25 minutes past the cycle-2 check. Blocklist polls
  complete every 5 minutes.
- E5: `mc admin user info m1lab tempo` shows the user, enabled, attached to
  `tempo_read_write`; `secret/default/tempo/minio` still resolves. Rollback
  path intact.
- E6: loki (submit 2026-04-26) and registry (submit 2026-09-01) both still
  running, both still holding static keys.
- `mc admin policy info m1lab tempo` returns `TempoOwnBucketOnly` on
  `arn:aws:s3:::tempo` and `arn:aws:s3:::tempo/*` only, matching
  `storage.tf` exactly.

## The three edits the briefing asked me to attack

**1. The "still keyed" enumeration is now exact.** `docs/workload-identity.md:269`
says loki, registry and memex still use their keys. `secrets.tf:31,42,53,104`
create exactly four MinIO KV entries (memex, loki, tempo, registry) and
`services.tf:232,275,482` render three of them into jobspecs; `tempo`'s is
no longer rendered. No fifth consumer exists: `backup-minio` uses the MinIO
ROOT credential (`deployments/infrastructure/backup.tf:65-70`), which is
outside this sentence's declared scope of `applications/storage.tf`, and
grafana/prometheus/haproxy reference the MinIO host without a storage.tf
key. A3 resolved.

**2. The six-name list has the right ORDER but the wrong COUNT.** I fetched
minio-go at the `v7.1.0` tag and read the providers. `pkg/credentials/env_minio.go`
`retrieve()` reads `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` first and only
falls back to `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY`, exactly as
`docs/workload-identity.md:375-376` now states. The chain order at doc:373
is also right: `tempodb/backend/s3/s3.go:686-698` at tempo `v2.10.8` builds
`Static, EnvAWS, EnvMinio, FileAWSCredentials, FileMinioClient, IAM`. B2 is
genuinely fixed. See finding C1 below for the residual undercount.

**3. The jobspec-only verification claim HOLDS.** This is the one the
briefing worried was "one wrong check swapped for another", and it is a
claim no gate and no eval row exercises, so I checked it against runtime
rather than from the diff. `nomad job inspect loki` — a job that still
renders MinIO keys from Vault — returns the template's `EmbeddedTmpl`
verbatim in the JSON, containing the literal strings `MINIO_ACCESS_KEY` and
`MINIO_SECRET_KEY`, with `Envvars: true` and `DestPath: secrets/minio.env`.
So a `template { env = true }` stanza really is part of the submitted
jobspec and really is greppable, and the same grep over `nomad job inspect
tempo` returns nothing. The claim at `docs/workload-identity.md:383` is
sound and is strictly better than the check it replaced, which the doc
itself says twice that Nomad refuses.

## Prior-cycle findings, re-attacked

Every cycle-2 finding was re-opened at its anchor this cycle; none was
auto-confirmed. Full detail in the ledger at
`.loop/scratch/R9-rollout-tempo-keyless-minio.adversarial/findings.json`.

- **B1 — CONFIRMED FIXED.** `modules/bucket/main.tf:11,29` emit
  `policy_read_write` and `policy_read_only` and `:47,54` attach both via
  `minio_iam_user_policy_attachment`; `storage.tf` holds no other
  `minio_iam_policy` and no attachment. "unlike the policies the bucket
  module emits" (storage.tf:100) is now accurate. The neighbouring claim
  that the module's `tempo_read_write` would not match claim mode is also
  right: `name_underscore` for `tempo` is `tempo`, so the module's policy
  is `tempo_read_write`, not `tempo`.
- **B2 — CONFIRMED FIXED** for the EnvMinio half, superseded by C1 for the
  EnvAWS half.
- **B3 — CONFIRMED FIXED.** No line in `tempo.hcl` exceeds 80, and no ADDED
  line anywhere in the diff exceeds 80.
- **A1, A2, A4, A9 — re-verified live this cycle**, not inherited. Evidence
  above. `tempo.hcl:96` carries only `-config.file`, and the live `Args`
  match.
- **A5, A6, A7, A8 — no change in scope, still hold.** services.tf:237
  still names storage.tf and the resource is there; services.tf:240-244
  parses and is accurate; tempo.hcl:61's "further down this file" is right
  (the schemeless `endpoint:` is at tempo.hcl:138, below tempo.hcl:60); the
  plan is untouched and only its frontmatter exceeds 80, which is
  pre-existing.
- **A10 — no change in scope, still holds.** `tempo.hcl:73` duplicates the
  address at `tempo.hcl:138`. Info; the plan specified the literal.
- **B4, B5 — no change in scope, still hold.** B4 is moot in fact: version
  2 has now written three times. B5's `services.tf:254` is still not
  itemized in plan section 7, still warranted by subticket 2.

## B6: I agree with you. It does not block.

You asked me to say plainly whether the cross-namespace concern blocks.
It does not, and I now have a stronger reason than "it's out of scope":
`nomad namespace list` returns only `default`. There is no second namespace
in which a same-named `tempo` job could exist, so the exposure today is
zero rather than merely accepted. The `claim_name = nomad_job_id` binding
is set on the MinIO job by M1, not by this diff, and this ticket's non-goal
3 excludes changing MinIO's OIDC configuration. `services.tf:254`'s
`depends_on` is the correct in-scope handling. Leave it as a follow-up.

## Findings

**C1 — LOW, non-blocking. The six-name list undercounts by two.**
Anchor: `docs/workload-identity.md:374-377`.

minio-go v7.1.0's `pkg/credentials/env_aws.go` `retrieve()` does not read
only the canonical pair. It sets `id = AWS_ACCESS_KEY_ID` and falls back to
`AWS_ACCESS_KEY` when that is empty, then `secret = AWS_SECRET_ACCESS_KEY`
falling back to `AWS_SECRET_KEY`. So eight variable names have to be
absent, not six, and doc:374's flat assertion "Six variable names have to
be absent, not two" is wrong by the same arithmetic that made the memex
edit necessary.

Note the shape of it: the cycle-2 text said "`EnvAWS` reads the `AWS_*`
pair", which was vague but did cover the legacy names. This cycle named
exactly two and pinned a count to them, turning a vague-but-covering phrase
into a specific undercount. That is the same species of defect as the
memex sentence you fixed, arriving in the fix itself.

Why it does not block: the ticket's own outcome is verified independently
of this sentence. All eight names return zero matches in the live
`nomad job inspect tempo`, no jobspec in this repo sets either legacy name,
and the eval's E2 row scores the four that exist in this repo's idiom. The
cost is confined to a checklist R10 and R11 will follow. The fix is one
clause and a digit; it belongs in whichever of those tickets touches this
section, or in a one-line follow-up.

**C2 — VERIFIED, no action.** The replacement verification claim at
doc:382-385 holds, on runtime evidence rather than inference. Residual and
info-only: "covers ... anything rendered from Vault" is true because every
Vault-rendering template in this repo spells the variable names literally
(`loki.hcl:68-69` is the live case I checked). A template that emitted
names dynamically would evade the grep. No such template exists here, so
this is a boundary on the claim, not an error in it.

**C3 — INFO.** `chain.go`'s `RetrieveWithCredContext` skips a provider only
when `AccessKeyID` AND `SecretAccessKey` are both empty. A stray
`AWS_ACCESS_KEY_ID` with no matching secret is therefore SELECTED, with an
empty secret, and web identity is never reached — a different symptom from
doc:377-379's "keeps using its old key while every check looks green". The
warning is correct for the fully-set case it describes; this is a nuance
worth a clause if the doc is edited anyway. No repo job sets these.

## Scope

Every changed line traces to the ticket. All four bound paths are declared
in plan section 7 (`tempo.hcl` at plan:104-124, `services.tf` at plan:125-126,
`storage.tf` at plan:127-130, the doc at plan:131-134). The doc edits stay
inside the declared "Keyless MinIO access" section (doc:263-396). No
unrelated file, resource or jobspec value moved. Nothing in the diff is
uncovered by both the gate and the eval except the prose and comments,
which I checked by hand above; the added doc lines are also clean on the
repo's slop rules (zero em dashes, no ` -- ` in prose, no British
spellings, no smart quotes, no tier-1 slop).
