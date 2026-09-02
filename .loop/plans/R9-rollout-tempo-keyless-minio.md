---
epic = "rollout"
depends_on = ["M1-minio-poc-service-account"]
priority = 20
summary = "Move the tempo job off its static MinIO access key onto Nomad Workload Identity, using minio-go's web-identity provider against MinIO's STS in claim mode. First real consumer of M1's mechanism; env-vars only, no code."
premise = { Q1 = "Tempo v2.10.8's credential chain reaches minio-go's IAM provider with an operator-settable STS endpoint, and minio-go v7.1.0's IAM provider performs AssumeRoleWithWebIdentity against it" }
measured_against = { Q1 = { kind = "package", version = "tempo v2.10.8 / minio-go v7.1.0", ref = "tempodb/backend/s3/s3.go L686-706; pkg/credentials/iam_aws.go L123-186" } }
---

# Ticket: R9-rollout-tempo-keyless-minio

## 1. Title

Move the tempo job off its static MinIO access key onto Nomad Workload
Identity, so the first real service holds no S3 credential.

## 2. Size / Effort

**Small.** Environment variables and deletions only. No new component, no
code, no image rebuild. The effort is in ordering the cutover and proving
the credential chain actually reached the new path rather than silently
falling back.

## 3. Triggered by

M1 landed keyless MinIO access and proved it with a throwaway job, then
tore that job down. Nothing uses the mechanism. Tempo is the first real
consumer: its client library supports the exchange natively, and its blast
radius (traces) is the smallest of the four static-key consumers.

## 4. Context

Tempo holds a long-lived MinIO access key today, brokered through Vault:

- `deployments/applications/services/tempo.hcl:74-84` — a `template` block
  renders `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` into the task
  environment from `secret "${tempo_minio_secret}"`.
- `deployments/applications/services/tempo.hcl:119-120` — the s3 backend
  config interpolates those two variables into `access_key` / `secret_key`.
- `deployments/applications/services/tempo.hcl:41` — `vault {}`. This is
  tempo's ONLY Vault use (grep for `secret` in that file returns lines 76,
  78, 120 and nothing else), so the block goes when the key does.
- `deployments/applications/services.tf:239-244` — `nomad_job.tempo` passes
  `tempo_minio_secret` into the templatefile call.
- `deployments/applications/storage.tf:23-28` — the `tempo` bucket entry,
  which provisions a `tempo` MinIO user with `generate_access_key = true`.
  The bucket module emits `tempo_read_write`
  (`deployments/applications/modules/bucket/main.tf:12`), attached to that
  user.

MinIO's side is already built. `deployments/infrastructure/services/minio.hcl`
carries the `NOMAD` OIDC target in claim mode
(`MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"`), so MinIO applies
the policy NAMED for the requesting job. No policy named `tempo` exists;
`tempo_read_write` is a different string and does not match.

## 5. Non-goals / out of scope

- Removing tempo's static key. The `tempo` MinIO user, its access key, and
  the Vault KV entry (`deployments/applications/secrets.tf:53-58`) all
  STAY, as the rollback path. Removing them is a follow-up once this has
  held in production.
- loki, registry and memex. Each has a different client and its own
  ticket (R10, R11, R12). This ticket touches no other job.
- Changing MinIO's OIDC configuration. M1 owns it and it needs no edit.
- Promoting the per-job policy convention into
  `deployments/applications/modules/bucket/`. That waits until more than
  one consumer proves it.

## 6. Requirements & restrictions

- R1. Tempo obtains MinIO credentials by exchanging its Workload Identity
  JWT, holding no static key. The named identity block follows the repo
  convention at `docs/workload-identity.md:160-186`: `name`, `aud`,
  `file`, a pinned `filepath`, and `change_mode = "noop"` (Nomad restarts
  on every renewal after the first, which a file-reading consumer does not
  need).
- R2. `aud = ["minio"]`, matching MinIO's
  `MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD`, because MinIO validates the
  audience in every mode. The audience registry at
  `docs/workload-identity.md:216` already assigns `minio` to this verifier.
- R3. A `minio_iam_policy` named exactly `tempo` (the job id) scoped to the
  `tempo` bucket, because claim mode applies the policy named by
  `nomad_job_id`. Scope the resource by bucket NAME as a plain string, not
  a cross-module reference: `minio_s3_bucket.bucket` lives inside
  `module.buckets`, which exports nothing
  (`deployments/applications/modules/bucket/outputs.tf` is empty), so it is
  not addressable from `storage.tf`. Mirror the statement shape at
  `deployments/applications/modules/bucket/main.tf:11-27`.
- R4. **Both static-credential sources must be removed, not just one.**
  Tempo's chain is ordered `Static`, `EnvAWS`, `EnvMinio`,
  `FileAWSCredentials`, `FileMinioClient`, `IAM`
  (`tempodb/backend/s3/s3.go` lines 686-706). `EnvMinio` reads
  `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` by those exact names, so leaving
  the env template in place while clearing the YAML keys leaves tempo
  authenticating with the static key and every check below passing. Delete
  the template block AND the two YAML keys.
- R5. Existing consumers stay untouched (CLAUDE.md section 3, surgical
  changes). loki, registry and memex keep their static keys and their
  Vault entries.

## 7. Code surface

- `deployments/applications/services/tempo.hcl:37-41` — add the named
  `identity` block to the `tempo` task (R1, R2), and DELETE `vault {}`
  (line 41), which becomes dead once the template goes.
- `deployments/applications/services/tempo.hcl:74-84` — DELETE the whole
  `template` block rendering `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`
  (R4).
- `deployments/applications/services/tempo.hcl:113-122` — add an `env`
  block to the task with exactly these two values, and DELETE the
  `access_key` / `secret_key` lines (119-120) from the s3 config:

  ```
  AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_minio.jwt"
  TEST_IAM_ENDPOINT           = "http://192.168.2.29:9000"
  ```

  **The scheme on `TEST_IAM_ENDPOINT` is load-bearing and does NOT match
  the form used two lines away.** `tempo.hcl:118` sets
  `endpoint: 192.168.2.29:9000` schemeless for the S3 client; copying that
  shape into `TEST_IAM_ENDPOINT` produces zero STS calls and silent
  anonymous S3 access with no diagnostic. Verified by probe against the
  pinned image during plan review.
- `deployments/applications/services.tf:239-244` — drop the now-unused
  `tempo_minio_secret` templatefile variable from `nomad_job.tempo`.
- `deployments/applications/storage.tf:86` — add `minio_iam_policy` named
  `tempo` immediately above `minio_iam_user.users` (R3), matching where M1
  put its throwaway equivalent. Leaves every other resource in the file
  alone, which is R5.
- `.loop/evals/R9-rollout-tempo-keyless-minio.md` — the eval marker, home
  of every scored check named in section 8.

## 8. Tests & validation gates

### Repo gate (loop-enforced)

`just pre_commit` (`.loop/config.json` `gates`), which runs the `nomad-fmt`
hook (`.pre-commit-config.yaml:16-21`), `terraform fmt -check -recursive`
(`:22-27`) and `scripts/tf_validate.sh` (`:28-33`) across all three roots.
There is no unit-test harness for this infrastructure and no CI workflow,
so this local gate plus the live evals below are the whole check surface.

**Worktree precondition.** `just worktree_setup <path>` (`justfile:45-48`)
first, or terraform in the worktree has no `prod.tfvars` for either root.

### Evals (live cluster)

Scored rows live in `.loop/evals/R9-rollout-tempo-keyless-minio.md`.

**`grafana/tempo:2.10.8` is DISTROLESS.** `/tempo` is the only executable;
there is no `/bin/sh` and no `/bin/ls`, confirmed by running the pinned
image during plan review. `nomad alloc exec` therefore CANNOT be used by
any row below, unlike M1's Alpine-based POC. Every check reads the
submitted jobspec, the alloc filesystem, or MinIO instead.

- E1 — tempo runs with a rendered WI JWT. `nomad job status tempo` shows
  one healthy allocation, and `nomad alloc fs <alloc> secrets/` lists
  `nomad_minio.jwt`.
- E2 — **no static credential remains reachable.** `nomad job inspect
  tempo` contains no `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`,
  `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID` or
  `AWS_SECRET_ACCESS_KEY`, and `nomad alloc fs <alloc> secrets/` shows no
  `minio.env`. The jobspec plus the rendered secrets dir are the only
  sources of task environment, so their absence there is absence in the
  environment. `MINIO_ROOT_*` are on the list because minio-go's
  `EnvMinio` provider checks those names FIRST (`env_minio.go` line 44),
  so omitting them from the check would leave a live fallback unscored.
  This row catches R4's silent fallback; without it every other row can
  pass on the old key.
- E3a — the exchange actually happens and MinIO accepts it. Within one
  `blocklist_poll` interval of the cutover, tempo's logs carry no
  `Access Denied` and no `AUTH: None`, and its blocklist poll completes.
  A successful LIST against the bucket is the earliest observable proof
  that the STS credentials work.
- E3b — a durable write lands. A new object appears under the `tempo`
  bucket (`mc ls --recursive m1lab/tempo`). Allow up to
  `max_block_duration` (`tempo.hcl:105` sets `30m`): tempo issues no PUT
  until it cuts a block, so this row is scored on a 30-minute horizon, not
  immediately after the apply.
- E4 — cross-bucket denial, checked INDEPENDENTLY of tempo. Perform the
  STS exchange directly with tempo's JWT (curl, as in
  `docs/workload-identity.md`), then use the returned credentials to list
  another bucket and expect `AccessDenied`. This must not be judged from
  tempo's own logs: per section 9(b), a missing policy and a real denial
  look identical from inside tempo, so only an independent exchange
  separates them.
- E5 — guardrail, rollback path intact. The `tempo` MinIO user, its access
  key, and the Vault KV entry at `default/tempo/minio` all still exist.
- E6 — guardrail, no collateral damage. loki and registry jobs are still
  running and still hold their static keys.

## 9. Risk assessment

- Blast radius: trace ingestion and query. Tempo is not on any other
  service's request path; losing it loses observability, not traffic. This
  is why tempo goes first.
- Reversibility: high, and the rollback path is deliberately preserved by
  non-goal 1. Restoring the template block, the two YAML keys and the
  templatefile variable returns tempo to the static key with one apply.
- Likeliest failure modes, all three of which fail QUIETLY: (a) the env
  template left in place, so `EnvMinio` wins and nothing actually changed
  (R4, caught by E2; proved by probe during plan review, where the static
  key signed every request and zero STS calls were made); (b) no
  `tempo`-named policy. Note this does NOT surface the way
  `docs/workload-identity.md:312-316` describes: that text covers a direct
  exchange, but tempo reaches STS through minio-go's credential CHAIN,
  which discards the provider error (`chain.go` line 61) and returns
  anonymous credentials (line 72). Tempo then logs a plain
  `Access Denied` and sends unsigned requests, which reads exactly like an
  ordinary permission problem. This is why E4 checks the denial through an
  independent exchange rather than through tempo; (c) `TEST_IAM_ENDPOINT`
  unset, or set without a scheme, so minio-go either falls back to
  `DefaultSTSRoleEndpoint` (`iam_aws.go` line 82,
  `https://sts.amazonaws.com`, since tempo passes no Region) or makes no
  STS call at all. Both end in silent anonymous access.
- Watch item, not a failure mode: the endpoint variable is named
  `TEST_IAM_ENDPOINT`. It is real shipped code in v2.10.8, not a debug
  stub, but the name invites an upstream rename. Pin the image and re-check
  on any tempo upgrade. See Q1.

## 10. Subtickets

1. **Add the `tempo` MinIO policy** (`storage.tf`) and apply. Depends on
   nothing; safe to land before the job changes, because a policy nothing
   references grants nothing.
2. **Cut the job over** (`tempo.hcl`, `services.tf`): identity block, env
   block, delete the template, the two YAML keys, the `vault {}` block and
   the templatefile variable. Apply. Depends on 1, or the exchange fails
   on a missing policy.
3. **Verify E1-E6** and record outcomes, including the R5 guardrail rows
   that loki, registry and memex are untouched. Depends on 2.

## 11. Open questions

- Q1. **`TEST_IAM_ENDPOINT` as the supported endpoint knob — resolved,
  with a watch.** The variable name suggests a test hook. Verified as real
  shipped behavior in the pinned release: `tempodb/backend/s3/s3.go` lines 698-702
  passes it as the IAM provider's `Endpoint`, and `iam_aws.go` lines 152-154
  uses a non-empty endpoint directly instead of the AWS fallback.
  Recommendation: proceed, pin the tempo image (already pinned at
  `tempo.hcl:60`), and re-run E3 on any tempo upgrade. Escalate to the
  operator if a future version drops it.
- Q2. **Whether to delete the static key in this ticket.** Recommendation:
  no. Keep it as the rollback path (non-goal 1) and remove it in a
  follow-up once this has held. Deleting it here makes the failure mode a
  re-provision rather than a re-apply.
- Q3. **`AWS_ROLE_ARN` deliberately unset.** Setting it would send a
  `RoleArn` and select role-policy mode, which pins every workload on that
  target to ONE policy and loses per-job scoping. Leaving it unset sends
  no RoleArn, which is claim mode (`iam_aws.go` lines 128-131 reads it from the
  environment and tolerates empty). Recommendation: leave unset; this is
  the whole reason M1 chose claim mode.

## Premises / assumptions

- **P1 — Tempo's credential chain reaches minio-go's IAM provider, and its
  STS endpoint is operator-settable.** Evidence:
  `tempodb/backend/s3/s3.go` lines 686-706 at tag `v2.10.8` (the pin at
  `tempo.hcl:60`), fetched from source: the chain is `Static`, `EnvAWS`,
  `EnvMinio`, `FileAWSCredentials`, `FileMinioClient`, then
  `credentials.IAM{Endpoint: os.Getenv("TEST_IAM_ENDPOINT")}`.
- **P2 — minio-go's IAM provider performs AssumeRoleWithWebIdentity against
  that endpoint and refreshes on expiry.** Evidence:
  `pkg/credentials/iam_aws.go` lines 123-186 at tag `v7.1.0` (tempo's pinned
  dependency): it reads `AWS_WEB_IDENTITY_TOKEN_FILE`, uses `m.Endpoint`
  directly when non-empty (skipping the `sts.<region>.amazonaws.com`
  fallback at 155-166), builds `STSWebIdentity` with `STSEndpoint`, re-reads
  the token file on each retrieve, and calls `SetExpiration`.
- **P3 — An empty `AWS_ROLE_ARN` yields claim mode.** Evidence:
  `iam_aws.go` lines 128-131 source `roleArn` from the environment and pass
  it through empty, and minio-go omits the parameter when it is empty
  (`sts_web_identity.go` line 150, `if len(roleARN) > 0`). M1 proved live
  that a no-RoleArn exchange returns credentials scoped by `nomad_job_id`;
  see `.loop/reflections/M1-minio-poc-service-account.md`.
- **P4 — MinIO's `NOMAD` target is in claim mode and expects a policy named
  for the job id.** Evidence:
  `deployments/infrastructure/services/minio.hcl` sets
  `MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD="nomad_job_id"`.
- **P5 — tempo's task can read its own JWT.** Evidence:
  `deployments/applications/services/tempo.hcl:39` sets `user = "root"`.
  The hazard documented at `docs/workload-identity.md:188-192` is a
  NON-root `user`, where Nomad's chown leaves the file unreadable; root is
  unaffected.
- **P6 — No policy named `tempo` exists today.** Evidence:
  `deployments/applications/modules/bucket/main.tf:12` emits
  `<bucket>_read_write` / `_read_only` only, so the existing name is
  `tempo_read_write`, which claim mode will not match.
