---
verdict: pass
tree: 0c6778a949abcb3d91b425d94ce64fa5585acd23
---

# Documentation freshness: R9-rollout-tempo-keyless-minio, cycle 3 (final)

No scope-binding lines. This briefing carried a tree fingerprint but no
64-hex scope digest, and the rule is to write only the digest I was given.
The verdict falls back to the whole-tree binding, which is stricter. The
reviewed path set was `deployments/applications/services.tf`,
`deployments/applications/services/tempo.hcl`,
`deployments/applications/storage.tf` and `docs/workload-identity.md`.

**Nothing blocks. Commit it.** All three required fixes are genuinely
fixed, not reworded, and I verified the load-bearing one against the
pinned upstream source rather than against the ticket's own account of it.
Four advisories below, none of which a reader can be misled by today.

## Required fixes: re-attacked and closed

### RF5 (DOC-R9-12): the enumeration of who is still keyed. FIXED.

`docs/workload-identity.md:269` = `provisioned as a rollback path. loki, registry and memex still use theirs.`

I checked the enumeration for completeness rather than taking it on
trust. Grepping every application jobspec for a rendered access key
returns exactly three: `services/loki.hcl:68-69`,
`services/registry.hcl:79-80`, `services/memex.hcl:125-126`. Tempo's
template is gone. The `ducklake_*`, `models_*` and `mlflow` keys are
minted in `storage.tf` but consumed by no job, so they are not "in use"
by anything the sentence could mean. `backup-minio` in the
infrastructure root uses the MinIO ROOT credential, which sits outside
this sentence's stated subject ("The static keys in
`deployments/applications/storage.tf`"). The list is complete.

### RF6 (DOC-R9-13): the six-name checklist and its order. FIXED.

`docs/workload-identity.md:375` = `   not two. \`EnvMinio\` checks \`MINIO_ROOT_USER\` and \`MINIO_ROOT_PASSWORD\``
`docs/workload-identity.md:376` = `   FIRST, then \`MINIO_ACCESS_KEY\` and \`MINIO_SECRET_KEY\`; \`EnvAWS\` reads`

Verified against minio-go v7.1.0 itself, fetched to
`.loop/scratch/R9-rollout-tempo-keyless-minio.documentation/minio-go/`.
`env_minio.go` reads `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD`, and
only when either is empty does it fall back to `MINIO_ACCESS_KEY` and
`MINIO_SECRET_KEY`. `env_aws.go` reads `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`. The order the doc states is the order the source
uses.

I also checked the provider order the same paragraph claims, which no
prior cycle had. `docs/workload-identity.md:373` says "static config,
`EnvAWS`, `EnvMinio`, files, and only then web identity". Tempo v2.10.8's
`tempodb/backend/s3/s3.go` `fetchCreds` builds exactly
`Static, EnvAWS, EnvMinio, FileAWSCredentials, FileMinioClient, IAM`.
Correct, word for word.

### RF7 (DOC-R9-14): the step-4 check. FIXED.

`docs/workload-identity.md:383` = `\`template { env = true }\` stanza is itself part of the submitted jobspec, so`

The rendered-secrets read is gone, so the instruction no longer asks for
something the same doc says Nomad refuses at `:328` and `:441`. The
replacement claim holds: `nomad job inspect` returns the template stanzas
with their embedded bodies, and all three remaining Vault-rendered MinIO
templates in this repo name the variables literally, so the jobspec grep
does catch them.

### Advisories from cycle 2: all three taken.

`:293-295` now reads "two things must line up. A job whose client library
does the exchange needs two more", which is consistent with "four things
rather than the two above" at `:347` and with the 4-item list under it,
whose first two items restate the two above. The semicolon at
`tempo.hcl:43` is gone. No line in `tempo.hcl` now exceeds 80 characters,
and neither does any added line anywhere in the diff.

### The adversarial pass's B1: also correct.

`deployments/applications/storage.tf:100` = `### No \`minio_iam_user_policy_attachment\`, unlike the policies the bucket`

`modules/bucket/main.tf` emits `policy_read_write` at `:11` and
`policy_read_only` at `:29`, and attaches both at `:47` and `:54`. The
revised comparison is true where the old "unlike every other policy here"
was not.

## No new contradiction

I read the changed doc section end to end looking for one, and read every
added comment against the doc it points at.

- The counts agree: two, plus two more, equals the four of the worked
  example, and items 1 and 2 of that list are the two above.
- The step-4 check no longer fights `:328` or `:441`.
- `tempo.hcl:44-47`'s `user = "root"` note agrees with the doc's
  non-root hazard at `:190-195`: Nomad chowns the JWT when a task sets
  `user`, which is only a problem when the process is unprivileged.
- `services.tf:236-238`'s new reason for the job living in this root
  (`minio_iam_policy.tempo_wi`) is true, and the resource is at
  `storage.tf:104`.
- Nothing else in `workload-identity.md` is falsified. `:127`'s
  bare-`vault {}` list never included tempo, and the audience registry's
  Owner column at `:216` names the introducing ticket, not the consumer.

## Every identifier resolves

Checked in this tree or in the pinned upstream: `tempo_wi` and its
`name = "tempo"` at `storage.tf:104-105`; `tempo_read_write` as the
module's emitted name; `vault_kv_secret_v2.tempo_minio_credentials` at
`secrets.tf:53`; `modules/bucket/outputs.tf` still zero bytes, so
`module.buckets` really exports nothing; the two env var names and values
at `tempo.hcl:72-73` matching `docs/workload-identity.md:357-358`
character for character; the schemeless `endpoint: 192.168.2.29:9000` at
`tempo.hcl:138` that the scheme warning contrasts against; the doc
section title quoted at `tempo.hcl:42-43` existing verbatim at
`workload-identity.md:121`; `TEST_IAM_ENDPOINT` as tempo's STS knob at
`s3.go:701`; `AWS_WEB_IDENTITY_TOKEN_FILE` and `AWS_ROLE_ARN` at
minio-go `iam_aws.go:123` and `:128`, with `RoleArn` set on the STS query
at `sts_web_identity.go:151`.

## No other doc is stale

Third sweep. `docs/monitoring.md:74` names the tempo bucket with no
credential claim. `observability-python.md`, `dash-landing-page.md`,
`haproxy_reverse_proxy.md`, `cluster-roles.md`, `cli-read-commands.md`,
`gcs-backups.md` and `vault-human-auth.md` mention tempo or MinIO without
a per-job credential claim. `README.md`, `ROADMAP.md` and `AGENTS.md`
name neither tempo's credentials nor R9. Nothing mentions
`-config.expand-env`.

## Doc rules on added lines

Zero `--` substitutions, zero smart quotes, zero tier-1 slop, zero
British spellings, zero self-narration, zero throat-clearing, zero
significance cluster, zero participial tails, zero emphasis crutches, and
every added line under 80 characters. One em dash appears in the diff, at
`services.tf:236`, and it is the pre-existing house-style title dash that
lines 228, 257, 281 and 366 of the same file already use.

## Advisories (not blocking, no action required to commit)

1. **DOC-R9-21. The absent-name list is eight, not six.** `env_aws.go`
   falls back to `AWS_ACCESS_KEY` and `AWS_SECRET_KEY` when the `_ID` and
   `_ACCESS_` spellings are empty, so those two names also defeat the web
   identity path. Not blocking: nothing in this tree sets either, they
   are deprecated AWS spellings, and step 4's bolded instruction
   ("Every static credential removed") already covers them. Related
   nuance: `chain.go` continues to the next provider only when the access
   key AND the secret are both empty, so a LONE `AWS_ACCESS_KEY_ID` sends
   the client anonymous rather than leaving it "using its old key" as
   `:377-379` says. That is a partial-config edge nobody writes on
   purpose.
2. **DOC-R9-22. Prose semicolon splice at `:376`**, joining
   "`MINIO_SECRET_KEY`" to "`EnvAWS` reads". The repo's own scan command
   misses it, because the backtick before the semicolon defeats the
   `\w;` pattern. The rule marks this low-confidence and surface-only,
   and the first clause carries an internal comma ("FIRST, then"), which
   is the rule's one durable keep. Flagged for consistency with cycle 2,
   where the same shape in `tempo.hcl` was fixed.
3. **DOC-R9-23. The chain order is Tempo's, not minio-go's.** `:373`
   attributes it to the library. Tempo builds the chain in `fetchCreds`.
   The order stated is right for tempo 2.10.8, so the only over-reach is
   `:348`'s "generalizes to any minio-go-based service", since each
   service picks its own provider list. Also at `:384`, "anything
   rendered from Vault" is slightly wider than the grep can promise: a
   template that ranges over Vault keys without naming them would slip
   through. All three in-repo templates name them.
4. **DOC-R9-26. Two tier-5 nits on added lines**, both defensible.
   "not just the one in the config file" at `:372` is contrastive
   negation, but the contrast is the whole point of step 4. "lives in" at
   `tempo.hcl:41` is a spatial copula that matches its neighbors
   (`storage.tf:97` has "lives inside `module.buckets`").

## Gate

Re-ran the non-mutating subset under the 5-minute bound, because this
cycle's fingerprint differs from the one on my cycle-2 trust stamp:
`nomad fmt -check -recursive` exit 0, `terraform fmt -check -recursive`
exit 0, EOF newline present on all four changed files. `terraform
validate` skipped (needs provider init). `.loop/stamp.json` records
`just pre_commit` exit 0 against this same fingerprint. Stamp refreshed at
`.loop/scratch/R9-rollout-tempo-keyless-minio.documentation/trust-stamp.json`.

Ledger updated: 47 entries, cycle 3 appended.
