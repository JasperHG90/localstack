---
epic = "minio"
depends_on = ["F1-foundation-nomad-wi-jwt-trust", "A1-audit-plan-premise-sweep"]
priority = 10
summary = "Prove keyless machine access to MinIO by wiring Nomad Workload Identity JWTs to a named identity_openid provider on the MinIO job, then having a throwaway consumer job assume STS credentials and read its bucket. Establishes the policy-name-equals-job-id convention."
tags = ["minio", "nomad", "jwt", "sts"]
---

# M1: MinIO OIDC POC — keyless machine access via Nomad Workload Identity

## 1. Title

Prove keyless machine access to MinIO by wiring Nomad Workload Identity
(WI) JWTs to a named `identity_openid` provider on the MinIO Nomad job,
then have a throwaway consumer job assume STS credentials and read its
bucket. Establish the per-job policy-name-equals-job-id convention.

## 2. Size / Effort

Medium. The MinIO env template change is small; the effort is in the
STS/OIDC trust wiring, running the POC end to end in two modes
(role-policy, then claim), and the verification unknowns MinIO's
deployed release forces us to confirm empirically.

## 3. Triggered by

Home-lab auth epic. We want machine identities (Nomad WI JWTs) to reach
MinIO without static access keys. Every current MinIO consumer injects a
static key pair from Vault (see Context). M1 is the machine-path POC and
depends on F1 (Nomad WI JWT trust chain: Nomad JWKS reachable, identity
stanza convention).

## 4. Context

Today MinIO auth is entirely static-key based.

- The MinIO server job is `deployments/infrastructure/services/minio.hcl`.
  Its only Vault-templated env block is `template { ... env = true }` at
  `deployments/infrastructure/services/minio.hcl:32-40`, injecting
  `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from Vault
  (`minio.hcl:34-35`) plus `MINIO_PROMETHEUS_AUTH_TYPE`. The task already
  has a `vault {}` stanza (`minio.hcl:30`). There is no OIDC / STS config
  anywhere in the job. Image is pinned at
  `minio.hcl:66` (`RELEASE.2025-09-07T16-13-09Z`). API is port 9000,
  console 9001 (`minio.hcl:18-25`).
- The job is instantiated in
  `deployments/infrastructure/services.tf:301-305`, passing only
  `minio_secret` (the Vault KV2 path for root creds).
- Bucket + IAM policy management lives in the reusable module
  `deployments/applications/modules/bucket/main.tf`. It emits, per
  bucket, a `minio_iam_policy` named `<name>_read_write`
  (`modules/bucket/main.tf:11-27`) and `<name>_read_only`
  (`main.tf:29-45`), then attaches them to named IAM **users** via
  `minio_iam_user_policy_attachment` (`main.tf:47-59`). Policy names are
  derived from the bucket name with hyphens replaced by underscores
  (`main.tf:2`). The module uses provider `aminueza/minio ~>3.8.0`
  (`modules/bucket/providers.tf:1-8`).
- Buckets are declared in
  `deployments/applications/storage.tf:2-29` (map `local.buckets`, e.g.
  the `memex` bucket at `storage.tf:11-16`) and instantiated via
  `module "buckets"` at `storage.tf:57-68`. Each named user gets a static
  access key via `minio_accesskey` (`storage.tf:51-55`).
- A representative consumer, `memex`, receives its MinIO key pair through
  its own `template { env = true }` block at
  `deployments/applications/services/memex.hcl:116-127`
  (`MEMEX_SERVER__FILE_STORE__ACCESS_KEY_ID` /
  `...__SECRET_ACCESS_KEY` templated from Vault). The consumer job is
  wired in `deployments/applications/services.tf:147-163`.

What is missing: no `identity` stanza exists on any Nomad job in the repo
(grep for `identity` across `deployments/**/*.hcl` returns nothing), and
MinIO has no `identity_openid` provider, so no keyless machine path
exists yet.

### Relayed finding: the deployed MinIO still supports OIDC and STS

Verified live against the running server on 2026-07-26. Recorded because
MinIO's `RELEASE.2025-05-24T17-08-30Z` notes say "External IDP logins via
LDAP/OIDC are removed as well; these are now available as part of the AiStor
Product", and this job runs a release **after** that date
(`RELEASE.2025-09-07T16-13-09Z`, `minio.hcl:66`). Read alone, that note reads
as though M1's whole mechanism was removed from the community server. **It was
not.** Do not re-litigate this from release notes; the server was asked
directly.

Evidence, all read-only against `192.168.2.29:9000` with the root credentials
from `secret/default/minio/localstack`:

- `mc admin config get <alias>` lists `identity_openid  enable OpenID SSO
  support` in the config subsystem, alongside `identity_ldap`.
- `mc admin config get <alias> identity_openid` returns the full key set,
  including the two this ticket depends on: **`role_policy`** (the
  policy-name-equals-job-id binding) and **`claim_name`** (defaulting to
  `policy`, the claim mode). Also present: `config_url`, `client_id`,
  `client_secret`, `scopes`, `vendor`, `redirect_uri_dynamic`,
  `user_id_claim`.
- The STS endpoint is live and role-aware: an unauthenticated
  `AssumeRoleWithWebIdentity` POST with a junk token returns
  `InvalidParameterValue: Role arn:minio:iam:::role/dummy-internal does not
  exist`, which is the response of a handler that exists and found no
  configured role, not of a removed feature.

This is a constraint, not a fork: it confirms M1's premise rather than opening
a decision, so M1 is not blocked. The one thing still worth doing inside M1 is
confirming the **behavior** rather than the config surface, since a key being
settable is not proof the flow works end to end on this release. That is
already M1's job, and its evals cover it.

## 5. Non-goals / out of scope

- The human path (Vault as OIDC provider for interactive S3 access). M1
  only wires the machine path. Vault-as-IdP is a sibling ticket; M1 must
  only leave room for it (multi-IdP), not implement it.
- Migrating any existing consumer (memex, loki, mlflow, ducklake) off
  static keys. Those static-key flows in `storage.tf` and the consumer
  jobs stay exactly as they are. M1 uses a **throwaway** consumer job.
- Zitadel or any external IdP (confirmed dropped for this epic).
- Production-grade policy rollout across all buckets. M1 demonstrates the
  convention on one bucket only.
- Changes to F1 (Nomad JWKS reachability / identity-stanza convention).
  M1 consumes F1's output; it does not build it.

## 6. Requirements & restrictions

Must achieve:

- R1. A named OIDC provider `nomad` on MinIO, configured entirely through
  the existing `template { env = true }` block in
  `deployments/infrastructure/services/minio.hcl:32-40`, pointing at
  Nomad's OIDC discovery / JWKS (from F1). No new template block; extend
  the existing one so the Vault-templated pattern is preserved.
- R2. A throwaway consumer Nomad job carrying
  `identity { aud = ["minio"] }` that calls STS
  `AssumeRoleWithWebIdentity` with its Nomad WI JWT and reads an object
  from its bucket.
- R3. Two-phase proof: **first** role-policy mode
  (`MINIO_IDENTITY_OPENID_ROLE_POLICY_NOMAD=<policy>` producing a
  `RoleArn`) to isolate whether Nomad-to-MinIO trust works at all;
  **then** claim mode (a JWT claim mapped to S3 policy names) for dynamic
  per-job RBAC. Do not skip phase one.
- R4. Adopt the convention: **MinIO policy name == `nomad_job_id`**.
  Because Nomad WI JWTs carry only fixed claims (`nomad_job_id`,
  `nomad_namespace`, `nomad_task`) and no custom claims, claim mode must
  map `nomad_job_id` to a policy of the same name. The existing
  `<bucket>_read_write` policy name (`modules/bucket/main.tf:12`) cannot
  be reused verbatim, so a per-job policy (or alias) named for the
  consuming job must be emitted (e.g. job `memex` to `s3:*` on the
  `memex` bucket only).
- R5. Extend `deployments/applications/modules/bucket/main.tf` (or add a
  parallel per-job policy resource) to emit a `minio_iam_policy` whose
  `name` equals the consuming job id, scoped to that bucket. Keep the
  existing `<name>_read_write` / `<name>_read_only` policies and their
  attachments untouched (surgical-change rule).

Restrictions the repo enforces (cited to where stated):

- All MinIO OIDC config flows through the MinIO job env template; secrets
  stay in Vault, never hardcoded (CLAUDE.md "Secrets: All in Vault KV2.
  Never hardcode credentials"). The JWKS URL is not a secret and may be a
  templatefile variable like `minio_secret` in
  `deployments/infrastructure/services.tf:304`.
- HCL must pass `nomad fmt -recursive` (`.pre-commit-config.yaml`
  `nomad-fmt` hook; root `justfile` `format` recipe).
- Match existing style; touch only what the change requires (CLAUDE.md
  sections 2 and 3). The bucket module currently attaches policies to
  IAM users; the new per-job policy is for an STS-assumed identity, so it
  needs no `minio_iam_user_policy_attachment`.
- Surface design forks rather than picking silently (CLAUDE.md section 1;
  the loop's `unresolved-design-fork` block). See Open Questions.

## 7. Code surface

- `deployments/infrastructure/services/minio.hcl:32-40` — extend the
  existing `template { env = true }` body to add the named
  `MINIO_IDENTITY_OPENID_*_NOMAD` env vars (config URL / discovery,
  client id matching `aud`, and in phase one `ROLE_POLICY_NOMAD`; in
  phase two `CLAIM_NAME_NOMAD=nomad_job_id`). Keep the root-cred lines
  (`minio.hcl:34-35`) unchanged.
- `deployments/infrastructure/services.tf:301-305` — if the Nomad JWKS /
  discovery URL is passed as a template variable, add it to the
  `templatefile(...)` vars map here alongside `minio_secret`.
- `deployments/applications/modules/bucket/main.tf:1-59` — add a per-job
  `minio_iam_policy` named for the consuming job (convention R4/R5),
  scoped to `minio_s3_bucket.bucket.id`, modeled on the existing
  `policy_read_write` block (`main.tf:11-27`). Thread a new variable
  through `modules/bucket/variables.tf` (job id(s) for the bucket) rather
  than overloading `permissions`.
- `deployments/applications/storage.tf:2-68` — supply the job-id input
  for the one POC bucket (the `memex` bucket at `storage.tf:11-16` is the
  natural candidate since a `memex`-named policy matches its job id).
- A **new throwaway** consumer job file (e.g.
  `deployments/applications/services/m1-poc.hcl`) with
  `identity { aud = ["minio"] }` and a task that runs the AWS/MinIO STS
  `AssumeRoleWithWebIdentity` call and a read, plus its `nomad_job`
  wiring in `deployments/applications/services.tf` modeled on the memex
  block (`services.tf:147-163`). This file is deleted when the POC
  concludes.

## 8. Tests & validation gates

### Repo gate (loop-enforced)

`just pre_commit` (root `justfile` `pre_commit` recipe, line 17-18, runs
`pre-commit run --all-files`). This is the gate named in
`.loop/config.json`. It is now Terraform-aware: `.pre-commit-config.yaml`
defines two `local` hooks with `types: [terraform]` in addition to the
HCL/JSON/YAML hooks:

- `terraform-fmt` (`.pre-commit-config.yaml:22-27`) runs
  `terraform fmt -check -recursive`.
- `terraform-validate` (`.pre-commit-config.yaml:28-33`) runs
  `scripts/tf_validate.sh`, which `terraform validate`s all three roots
  this ticket touches — `deployments/infrastructure`,
  `deployments/applications`, and
  `deployments/applications/modules/bucket` — offline
  (`init -backend=false`, no Consul state, no credentials).

So a syntax/type error in any `.tf` this ticket edits fails `just
pre_commit`; the earlier "Terraform is not validated by the gate" caveat
no longer holds and is removed. The HCL job files are still covered by
the `nomad-fmt` hook (`.pre-commit-config.yaml:16-21`). `just pre_commit`
must pass before declaring done. There is no CI workflow, so this local
gate is the whole automated check surface.

There is no automated unit-test harness for this infra (the
`python-testing.md` rule governs Python packages, of which this change
has none). Beyond the gate, M1's acceptance is a live end-to-end proof.

### Evals (live cluster)

The cluster is reachable this session: `VAULT_ADDR` / `VAULT_TOKEN`,
`NOMAD_ADDR` / `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set, so the
acceptance below is runnable, not hypothetical. Each eval gives a command
and its expected result. `<alias>` is the `mc` alias for the MinIO API
(port 9000); `<alloc>` is the throwaway job's allocation id; substitute
the real MinIO endpoint and bucket names as deployed.

**Dependency marker.** Every eval below requires **F1 applied first**
(Nomad OIDC discovery/JWKS reachable from the MinIO container and the
identity-stanza convention in place). Without F1 the WI JWT has no trust
anchor and all STS calls fail with an OIDC/JWKS error. The per-eval
"needs" line names the additional subtickets that must be applied.

- E1 — OIDC provider present (phase one). Needs: F1 + subticket 2.
  Command: `mc admin config get <alias> identity_openid`
  (or the MinIO admin API equivalent).
  Expected: a `nomad`-named `identity_openid` block whose `config_url`
  is Nomad's OIDC discovery URL, `client_id=minio` (matching
  `aud=["minio"]`), and `role_policy` set to the phase-one policy. No
  `claim_name` yet.

- E2 — throwaway consumer running. Needs: F1 + subtickets 2, 3.
  Command: `nomad job status m1-poc`
  Expected: `Status = running` with one healthy allocation; its
  `identity` stanza renders the WI JWT (per F1's convention, e.g. to
  `secrets/nomad_minio.jwt`).

- E3 — STS AssumeRoleWithWebIdentity, role-policy mode (phase one).
  Needs: F1 + subtickets 2, 3.
  Command (from inside the alloc, aws-cli form):
  `nomad alloc exec <alloc> aws sts assume-role-with-web-identity
  --role-arn <RoleArn-from-E1> --role-session-name m1
  --web-identity-token "$(cat secrets/nomad_minio.jwt)"
  --endpoint-url http://<minio>:9000`
  Expected: JSON with `Credentials` (`AccessKeyId`, `SecretAccessKey`,
  `SessionToken`) and a short `Expiration`. This isolates that
  Nomad-to-MinIO trust works before any per-job RBAC. Do not proceed to
  claim mode until E3 passes.

- E4 — read own bucket with the STS creds (phase one). Needs: F1 +
  subtickets 2, 3.
  Command (export the E3 creds as `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`, then):
  `aws s3 ls s3://memex --endpoint-url http://<minio>:9000`
  Expected: the object listing returns (exit 0). Proves the assumed
  identity can read its target bucket.

- E5 — claim mode, per-job policy = `nomad_job_id` (phase two). Needs:
  F1 + subtickets 2, 3, 4, 5. Precondition: a `minio_iam_policy` named
  exactly `m1-poc` (the job id) scoped to the `memex` bucket exists
  (R4/R5), and MinIO is switched to `CLAIM_NAME_NOMAD=nomad_job_id`
  (`ROLE_POLICY_NOMAD` removed).
  Command: repeat E3 with **no** `--role-arn` (claim mode derives the
  policy from `nomad_job_id`), export the returned creds, then
  `aws s3 ls s3://memex --endpoint-url http://<minio>:9000`
  Expected: listing succeeds, proving the job id mapped to a same-named
  policy with no `RoleArn`.

- E6 — cross-bucket denial (phase two, proves per-job scoping). Needs:
  F1 + subtickets 2, 3, 4, 5.
  Command (reusing the E5 claim-mode creds):
  `aws s3 ls s3://<other-bucket> --endpoint-url http://<minio>:9000`
  Expected: `AccessDenied`. Together E5 + E6 prove the per-job policy
  (name == `nomad_job_id`) grants exactly its own bucket and nothing
  else.

- E7 — multi-IdP shape. Needs: F1 + subtickets 2, 6.
  Command: `mc admin config get <alias> identity_openid`
  Expected: two named `identity_openid` configs coexist (the `nomad`
  config plus a placeholder second named config), confirming the
  multi-IdP shape is real and leaves room for the Vault-as-IdP sibling
  ticket, not assumed.

Record E1–E7 outcomes in the ticket's closing notes. Run
`nomad fmt -recursive` and `just pre_commit` (both must be green) before
declaring done.

The live acceptance above is captured as the loop eval marker at `.loop/evals/M1-minio-poc-service-account.md` (co-author with the `create-eval` skill before implementation; `require_eval` is set, so the loop refuses pickup until it exists).

## 9. Risk assessment

- Blast radius: the MinIO server job is shared infrastructure. Editing
  `minio.hcl` and re-applying `deployments/infrastructure` restarts the
  MinIO task, briefly interrupting every S3 consumer (memex, loki,
  mlflow, ducklake). Adding OIDC env vars should not affect existing
  static-key auth, but a malformed `MINIO_IDENTITY_OPENID_*` value can
  make MinIO refuse to start. Validate the env block and have the prior
  job version ready to roll back.
- The bucket-module change runs in `deployments/applications`. A new
  `minio_iam_policy` is additive; the risk is a name collision if a
  job-id-named policy already overlaps an existing `<name>_read_write`
  name. Guard against emitting duplicate policy names.
- Reversibility: high. Remove the OIDC env vars and re-apply to restore
  the prior MinIO state; delete the throwaway job and the per-job policy.
  No data migration, no state destruction.
- Likeliest failure modes: (a) Nomad JWKS not reachable from the MinIO
  container (an F1 dependency, not M1); (b) `aud` mismatch between the
  identity stanza and MinIO's configured client id; (c) claim mode
  expecting a policy-name claim value that the fixed `nomad_job_id` claim
  does not format as MinIO wants; (d) the deployed MinIO release
  (`minio.hcl:66`) differing from docs on multi-IdP or claim mapping.

## 10. Subtickets

1. **F1 dependency check** — confirm Nomad OIDC discovery / JWKS endpoint
   is reachable from the MinIO task and note the exact URL and the
   identity-stanza convention F1 defines. Blocks all below.
2. **MinIO OIDC provider, role-policy mode** — extend
   `minio.hcl:32-40` with `MINIO_IDENTITY_OPENID_*_NOMAD`
   (config URL, client id = `minio`, `ROLE_POLICY_NOMAD`); thread the
   JWKS URL var through `services.tf:301-305` if needed; re-apply. Depends
   on 1.
3. **Throwaway consumer job** — add `m1-poc.hcl` with
   `identity { aud = ["minio"] }` and an STS
   `AssumeRoleWithWebIdentity` + `GetObject` step; wire it in
   `services.tf`. Verify V1. Depends on 2.
4. **Per-job policy in the bucket module** — extend
   `modules/bucket/main.tf` (+ `variables.tf`) to emit a
   `minio_iam_policy` named for the consuming job; supply the input from
   `storage.tf`. Depends on 1 (convention).
5. **Switch MinIO to claim mode** — replace `ROLE_POLICY_NOMAD` with
   `CLAIM_NAME_NOMAD=nomad_job_id`; verify V2 (own-bucket read
   allowed, other-bucket denied). Depends on 3 and 4.
6. **Multi-IdP shape check** — verify V3 (two named OIDC configs
   coexist). Depends on 2.
7. **Tear down** — delete `m1-poc.hcl` and its wiring; record V1–V3
   outcomes and the confirmed convention. Depends on 5 and 6.

## 11. Open questions

Each fork below is unresolved by the request, the repo, or F1, and needs
an operator decision before or during the loop.

- Q1. **Nomad OIDC discovery URL and TLS.** The exact discovery/JWKS URL
  and whether MinIO trusts its TLS chain are F1 outputs not yet in the
  repo. Recommendation: block subticket 2 on F1 providing a concrete,
  reachable URL; do not hardcode a guessed endpoint.
- Q2. **Claim-mode policy-name mapping for a fixed claim.** MinIO claim
  mode expects the mapped claim's value to be a comma-separated list of
  policy names. `nomad_job_id` yields a single job id string. Confirm
  against the deployed release (`minio.hcl:66`) that a bare job-id string
  in `nomad_job_id` maps cleanly to a same-named policy. Recommendation:
  verify empirically in subticket 5; if MinIO needs a policy-claim
  formatting shim, surface it rather than inventing a claim.
- Q3. **Where the per-job policy lives.** Extend the existing
  `modules/bucket/` module (adds a job-id input to every bucket) versus a
  separate `minio_iam_policy` resource in `storage.tf` for POC buckets
  only. Recommendation: for the POC, add the resource in `storage.tf`
  scoped to the one bucket to keep the shared module stable; promote it
  into the module only once the convention is proven.
- Q4. **Location and lifecycle of the throwaway job.** Placing
  `m1-poc.hcl` under `deployments/applications/services/` versus a
  scratch/POC subdir. Recommendation: `deployments/applications/services/`
  with an explicit `m1-poc` name and a teardown subticket (7), so it is
  obviously temporary and removed on completion.
- Q5. **`aud` / client-id value.** The request fixes `aud = ["minio"]`;
  MinIO's `MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD` must match. Confirm
  MinIO validates `aud` for the WI JWT in the deployed release.
  Recommendation: set client id to `minio` and verify in subticket 2;
  if MinIO ignores `aud` in role-policy mode, note it for the claim-mode
  switch.
- Q6. **STS tooling inside the throwaway job.** Which client performs
  `AssumeRoleWithWebIdentity` (mc, aws-cli, a small script). The repo has
  no established pattern. Recommendation: use the smallest client that the
  POC image already ships; record the exact call for reuse in later
  epic tickets.
