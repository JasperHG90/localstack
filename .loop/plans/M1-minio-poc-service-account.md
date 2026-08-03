---
epic = "minio"
depends_on = ["F1-foundation-nomad-wi-jwt-trust", "A1-audit-plan-premise-sweep", "F10-foundation-nomad-oidc-issuer"]
priority = 10
summary = "Prove keyless machine access to MinIO by wiring Nomad Workload Identity JWTs to a named identity_openid provider on the MinIO job, then having a throwaway consumer job assume STS credentials and read its bucket. Establishes the policy-name-equals-job-id convention."
tags = ["minio", "nomad", "jwt", "sts"]
---

# Ticket: M1-minio-poc-service-account — MinIO OIDC POC: keyless machine access via Nomad Workload Identity

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
  `deployments/infrastructure/services.tf:306-311`, passing only
  `minio_secret` (the Vault KV2 path for root creds).
- Bucket + IAM policy management lives in the reusable module
  `deployments/applications/modules/bucket/main.tf`. It emits, per
  bucket, a `minio_iam_policy` named `<name>_read_write`
  (`deployments/applications/modules/bucket/main.tf:11-27`) and
  `<name>_read_only` (`main.tf:29-45`), then attaches them to named IAM
  **users** via `minio_iam_user_policy_attachment` (`main.tf:47-59`).
  Policy names are derived from the bucket name with hyphens replaced by
  underscores (`main.tf:2`). The module uses provider
  `aminueza/minio ~>3.8.0`
  (`deployments/applications/modules/bucket/providers.tf:1-8`).
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
  wired in `deployments/applications/services.tf:159-179`.

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

- R1. A named OIDC provider `NOMAD` on MinIO, configured entirely through
  the existing `template { env = true }` block in
  `deployments/infrastructure/services/minio.hcl:32-40`, pointing at
  Nomad's OIDC discovery / JWKS (from F1). No new template block; extend
  the existing one so the Vault-templated pattern is preserved.
  **Target name is uppercase, not a style choice.** MinIO derives the
  target name verbatim from the trailing env-var segment
  (`internal/config/config.go`: `GetAvailableTargets` / `getEnvVarName`
  do no case-folding). An idiomatic uppercase env var like
  `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD` therefore names the target
  `NOMAD`, never `nomad`. Every reference to the provider name in this
  plan and its eval marker uses `NOMAD` for that reason.
- R2. A throwaway consumer Nomad job carrying a **named** `identity` block
  (per F1's convention, `docs/workload-identity.md:132-153`: an unnamed
  block configures the task's default Nomad-API identity and writes no
  JWT to disk):
  ```
  identity {
    name        = "minio"
    aud         = ["minio"]
    file        = true
    change_mode = "restart"
  }
  ```
  This writes the WI JWT to `secrets/nomad_minio.jwt` inside the alloc.
  The task calls STS `AssumeRoleWithWebIdentity` with that JWT and reads
  an object from its bucket.
- R3. Two-phase proof: **first** role-policy mode
  (`MINIO_IDENTITY_OPENID_ROLE_POLICY_NOMAD=<policy>` producing a
  `RoleArn`) to isolate whether Nomad-to-MinIO trust works at all;
  **then** claim mode (a JWT claim mapped to S3 policy names) for dynamic
  per-job RBAC. Do not skip phase one.
- R4. Adopt the convention: **MinIO policy name == `nomad_job_id`**.
  Because Nomad WI JWTs carry only fixed claims (`nomad_job_id`,
  `nomad_namespace`, `nomad_task`) and no custom claims, claim mode must
  map `nomad_job_id` to a policy of the same name. The existing
  `<bucket>_read_write` policy name
  (`deployments/applications/modules/bucket/main.tf:12`) cannot be reused
  verbatim, so a per-job policy (or alias) named for the consuming job
  must be emitted (e.g. job `memex` to `s3:*` on the `memex` bucket only).
- R5. Add a `minio_iam_policy` resource in `storage.tf`, scoped by bucket
  name (a plain string, not a cross-module resource reference — the
  `minio_s3_bucket.bucket` resource lives inside `module.buckets` and is
  not addressable from `storage.tf`) to the one POC bucket, whose `name`
  equals the consuming job id (resolves Q3: the shared
  `deployments/applications/modules/bucket/main.tf` module stays
  untouched for this POC; promote the pattern into the module only once
  the convention is proven on one bucket). Keep the existing
  `<name>_read_write` / `<name>_read_only` policies and their attachments
  untouched (surgical-change rule).

Restrictions the repo enforces (cited to where stated):

- All MinIO OIDC config flows through the MinIO job env template; secrets
  stay in Vault, never hardcoded (CLAUDE.md "Secrets: All in Vault KV2.
  Never hardcode credentials"). The JWKS URL is not a secret and may be a
  templatefile variable like `minio_secret` in
  `deployments/infrastructure/services.tf:309`.
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
- `deployments/infrastructure/services.tf:306-311` — if the Nomad JWKS /
  discovery URL is passed as a template variable, add it to the
  `templatefile(...)` vars map here alongside `minio_secret`
  (`services.tf:309`).
- `deployments/applications/storage.tf:2-68` — add a `minio_iam_policy`
  resource named for the consuming job (convention R4/R5), scoped by
  bucket **name** (a plain string, `"memex"`, not a cross-module resource
  reference — the `minio_s3_bucket.bucket` resource lives inside
  `module.buckets` and is not addressable from `storage.tf`), modeled on
  the module's own ARN construction
  (`arn:aws:s3:::<bucket-name>` /
  `arn:aws:s3:::<bucket-name>/*`, see
  `deployments/applications/modules/bucket/main.tf:11-27`). The `memex`
  bucket entry at `storage.tf:11-16` is the natural candidate since a
  `memex`-named policy matches its job id. This is a `storage.tf`-local
  resource, not a module change (R5/Q3): the shared
  `deployments/applications/modules/bucket/` module stays untouched.
- A **new throwaway** consumer job file (e.g.
  `deployments/applications/services/m1-poc.hcl`) with the named
  `identity { name = "minio" aud = ["minio"] file = true }` block (R2) and
  a task that runs the AWS/MinIO STS `AssumeRoleWithWebIdentity` call and a
  read, plus its `nomad_job`
  wiring in `deployments/applications/services.tf` modeled on the memex
  block (`services.tf:159-179`). This file is deleted when the POC
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

**Precondition if run in a fresh git worktree.**
`deployments/infrastructure/services.tf:290` calls
`file("${path.root}/../../.ssh/id_rsa")`, evaluated statically by
`terraform validate`. `git worktree add` checks out tracked files only,
so a fresh worktree has no `.ssh/id_rsa` and `terraform-validate` fails
before it ever reaches this ticket's changes. Run `just worktree_setup
<path>` (`justfile:40-42`) first to symlink `.ssh` and copy
`prod.tfvars` into the worktree.

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
  Expected: a `NOMAD`-named `identity_openid` block whose `config_url`
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
  Expected: two named `identity_openid` configs coexist (`NOMAD` plus a
  second named target, e.g. `POC2`, pointed at the SAME Nomad discovery
  URL under a different `client_id`). **Not a placeholder pointed at a
  fake or unreachable URL**: `openid.go`'s `LookupConfig` fails the
  entire config load, for every target, the moment ANY one target's
  discovery document fails to parse. A broken placeholder would take
  down the working `NOMAD` target too. Use a second real, reachable
  discovery document instead, confirming the multi-IdP shape is real
  without risking the live provider.

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
- The `storage.tf` change runs in `deployments/applications`. A new
  `minio_iam_policy` is additive; the risk is a name collision if a
  job-id-named policy already overlaps an existing `<name>_read_write`
  name. Guard against emitting duplicate policy names.
- Subticket 6 (multi-IdP shape, E7) touches the SAME `minio.hcl` env
  block that already carries the working `NOMAD` provider. MinIO's
  `openid.go` `LookupConfig` aborts the **entire** OIDC config load, for
  every target, the moment any one target's discovery document fails to
  parse. A placeholder second target pointed at a fake or unreachable
  URL would take down the live `NOMAD` provider along with it. Point the
  second target at a real, reachable discovery document (subticket 6).
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
   JWKS URL var through `services.tf:306-311` if needed; re-apply. Depends
   on 1.
3. **Throwaway consumer job** — add `m1-poc.hcl` with the named
   `identity { name = "minio" aud = ["minio"] file = true }` block (R2)
   and an STS `AssumeRoleWithWebIdentity` + `GetObject` step; wire it in
   `services.tf`. Verify V1. Depends on 2.
4. **Per-job policy in `storage.tf`** — add a `minio_iam_policy` resource
   in `storage.tf`, named for the consuming job and scoped to the `memex`
   bucket; the shared `modules/bucket/` module stays untouched (R5/Q3).
   Depends on 1 (convention).
5. **Switch MinIO to claim mode** — replace `ROLE_POLICY_NOMAD` with
   `CLAIM_NAME_NOMAD=nomad_job_id`; verify V2 (own-bucket read
   allowed, other-bucket denied). Depends on 3 and 4.
6. **Multi-IdP shape check** — add a second named `identity_openid`
   target (e.g. `POC2`) pointed at the SAME reachable Nomad discovery
   URL under a different `client_id` (never a fake/unreachable URL: a
   parse failure on one target aborts MinIO's entire OIDC config load,
   per `openid.go`'s `LookupConfig`); verify V3 (two named OIDC configs
   coexist, `NOMAD` still working). Depends on 2.
7. **Tear down** — delete `m1-poc.hcl` and its wiring; record V1–V3
   outcomes and the confirmed convention. Depends on 5 and 6.

## 11. Open questions

Each fork below is unresolved by the request, the repo, or F1, and needs
an operator decision before or during the loop.

- Q1. **Nomad OIDC discovery URL and TLS.** The exact discovery/JWKS URL
  and whether MinIO trusts its TLS chain are F1 outputs not yet in the
  repo. Recommendation: block subticket 2 on F1 providing a concrete,
  reachable URL; do not hardcode a guessed endpoint.
  **Relayed from F10-foundation-nomad-oidc-issuer (2026-08-03).** F10 owns
  setting `server { oidc_issuer = "https://nomad.lab.orangecluster.nl" }`
  in `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`, which makes
  Nomad serve `/.well-known/openid-configuration`. The discovery URL M1
  points MinIO's `identity_openid` `config_url` at is therefore
  `https://nomad.lab.orangecluster.nl/.well-known/openid-configuration`,
  served over HTTPS through the HAProxy edge (publicly-trusted Let's
  Encrypt wildcard from T1/T3), reachable from the MinIO node
  (192.168.2.29). F1 delivers JWKS only and does NOT enable discovery;
  F10 is the owner. Once F10 is `done`, M1's `config_url` is this concrete
  value, not a guess. The existing `unresolved-design-fork` block on M1
  (MinIO removed `jwks_url`, only `config_url` works) is the one this
  relay resolves: F10 produces the discovery document M1 requires.
- Q2. **Claim-mode policy-name mapping for a fixed claim.** MinIO claim
  mode expects the mapped claim's value to be a comma-separated list of
  policy names. `nomad_job_id` yields a single job id string. Confirm
  against the deployed release (`minio.hcl:66`) that a bare job-id string
  in `nomad_job_id` maps cleanly to a same-named policy. Recommendation:
  verify empirically in subticket 5; if MinIO needs a policy-claim
  formatting shim, surface it rather than inventing a claim.
- Q3. **Where the per-job policy lives — resolved.** Extending the shared
  `deployments/applications/modules/bucket/` module (a job-id input on
  every bucket) versus a separate `minio_iam_policy` resource in
  `storage.tf` for the POC bucket only. **Resolved: `storage.tf`-local**
  (R5, subticket 4, code surface). Keeps the shared module stable while
  the convention is unproven; promote it into the module only once M1
  closes.
- Q4. **Location and lifecycle of the throwaway job.** Placing
  `m1-poc.hcl` under `deployments/applications/services/` versus a
  scratch/POC subdir. Recommendation: `deployments/applications/services/`
  with an explicit `m1-poc` name and a teardown subticket (7), so it is
  obviously temporary and removed on completion.
- Q5. **`aud` / client-id value — resolved.** The request fixes
  `aud = ["minio"]`; MinIO's `MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD` must
  match. Confirmed via `jwt.go`'s `Validate` (called unconditionally in
  both role-policy and claim modes): MinIO always validates `aud`, in
  every mode. Set client id to `minio` in subticket 2.
- Q6. **STS tooling inside the throwaway job.** Which client performs
  `AssumeRoleWithWebIdentity` (mc, aws-cli, a small script). The repo has
  no established pattern. Recommendation: use the smallest client that the
  POC image already ships; record the exact call for reuse in later
  epic tickets.

## Premises / assumptions

- **P1 — Nomad now serves a real OIDC discovery document, and the URL is
  concrete.** F10 shipped `server { oidc_issuer =
  "https://nomad.lab.orangecluster.nl" }`
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:42`,
  `bootstrap/playbooks/configure_hashistack_server.yml:45`). Probe:
  `curl https://nomad.lab.orangecluster.nl/.well-known/openid-configuration`
  returns HTTP 200 with a populated `issuer` and `jwks_uri`, re-verified
  2026-08-03. MinIO's `config_url` (R1) points at this exact URL.
- **P2 — MinIO's `identity_openid` accepts only `config_url`, never
  `jwks_url`, on the deployed release.** The deployed image
  (`RELEASE.2025-09-07T16-13-09Z`, `minio.hcl:66`) removed `jwks_url` from
  `internal/config/identity/openid/openid.go`; only a real discovery
  document works. P1 supplies that document, so this premise no longer
  blocks the ticket.
- **P3 — The consumer job's `identity` block must be NAMED, with
  `file = true`, to land a JWT on disk.** Anchor:
  `docs/workload-identity.md:132-153`, which states an unnamed
  `identity {}` configures the task's default Nomad-API identity, not a
  retargeted one, and writes no JWT to disk. Probe: verified live on Nomad
  2.0.4. R2 now specifies the named block (`name = "minio"`,
  `aud = ["minio"]`, `file = true`), which writes
  `secrets/nomad_minio.jwt`.
- **P4 — The deployed MinIO release still supports OIDC/STS despite
  ambiguous release notes.** Probe: verified live 2026-07-26 against
  `192.168.2.29:9000`: `mc admin config get <alias> identity_openid` lists
  the config subsystem, and an unauthenticated
  `AssumeRoleWithWebIdentity` returns a role-not-found error, not a
  removed-feature error (see `## 4. Context`, "Relayed finding").
- **P5 — F1 delivers JWKS and the identity-stanza convention; F10 delivers
  discovery. Both are `done`.** Probe: `.loop/ledger.json` shows
  `F1-foundation-nomad-wi-jwt-trust`, `A1-audit-plan-premise-sweep`, and
  `F10-foundation-nomad-oidc-issuer` all at stage `done`, closing the fork
  Q1 raised.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: BROKEN. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/M1-minio-poc-service-account.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: MinIO RELEASE.2025-09-07 REMOVED `jwks_url`; only `config_url` (a real discovery document) works, and Nomad's discovery endpoint is disabled. No ticket owns setting `oidc_issuer`. Separately, the unnamed `identity` stanza writes no JWT to the alloc.

This ticket is **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reverse design decisions or need an
operator call. **Do not implement from this plan as written.** Work the
verdict's required-fix list, then re-dispatch `loop-plan-reviewer` before
unblocking.

## Plan review, 2026-08-03 (fixes applied, re-dispatched)

`loop-plan-reviewer` re-ran against this plan and the live cluster. Verdict
stayed `fail` on that pass, for two grounds separate from the ones this
section closes: `loopctl verify-plan` hard-fails on bare `modules/bucket/*`
citations, a missing `## Premises` section, and the header not matching the
`# Ticket: <slug>` convention.

Fixed in this edit:

- Header changed to `# Ticket: M1-minio-poc-service-account — ...`.
- Every bare `modules/bucket/*` citation now reads
  `deployments/applications/modules/bucket/*`.
- Added the `## Premises / assumptions` section above, closing ground #1
  (F10 makes `config_url` reachable and correctly shaped, confirmed live)
  and ground #2 (R2, the code-surface item, and subticket 3 now specify the
  named `identity { name = "minio" aud = ["minio"] file = true }` block per
  `docs/workload-identity.md:132-153`, instead of the unnamed form that
  writes no JWT to disk).

Not yet re-verified by an agent: re-dispatch `loop-plan-reviewer` before
unblocking this ticket from `blocked`.

## Plan review, 2026-08-03 continued (second fix round)

`loop-plan-reviewer` re-ran again. Verdict: `fail` (premise **PARTIALLY
SOUND**, upgraded from BROKEN). P1-P5 all held on independent
re-verification, including the named `identity` block (the single most
dangerous prior break). Six items from the ORIGINAL 2026-07-30 A1 sweep
verdict, never touched by the first fix round, still gated the verdict:

- **Provider name case.** MinIO derives the target name verbatim from the
  env-var suffix; an idiomatic uppercase env var names the target `NOMAD`,
  not `nomad`. Fixed: R1, the code-surface item, subticket 2, E1, and the
  eval marker's row 1 now all say `NOMAD`.
- **Multi-IdP placeholder aborting MinIO's whole config load.** MinIO's
  `LookupConfig` fails the ENTIRE config load if any one target's discovery
  document fails to parse; a placeholder second config pointed at a fake
  URL would take down the working `NOMAD` target too. Fixed: E7, subticket
  6, the eval marker's row 6, and a new risk-assessment bullet now require
  the second target to point at a real, reachable discovery document
  (e.g. the same Nomad URL, a different `client_id`), never a placeholder.
- **Missing `worktree_setup` gate precondition.**
  `deployments/infrastructure/services.tf:290`'s `file(".ssh/id_rsa")` is
  evaluated statically by `terraform validate`, and a fresh git worktree
  has no `.ssh/id_rsa`. Fixed: added a precondition note to `## 8. Tests &
  validation gates` naming `just worktree_setup <path>`.
- **Drifted `services.tf` anchors.** `deployments/infrastructure/services.tf`'s
  `minio` job resource had moved to lines 306-311 (not 301-305); the
  `memex` job resource in `deployments/applications/services.tf` had moved
  to lines 159-179 (not 147-163). Fixed: every citation to both updated.
- **Q3-vs-subticket-4 contradiction.** Q3 recommended a `storage.tf`-local
  policy resource; subticket 4, R5, and the code-surface item unconditionally
  committed to extending the shared bucket module. Fixed: resolved toward
  Q3's recommendation everywhere (R5, code surface, subticket 4, Q3 itself
  now all say `storage.tf`-local; the shared module stays untouched).
- **Q5's dead "if MinIO ignores `aud`" branch.** MinIO's `jwt.go` `Validate`
  runs unconditionally in every mode; MinIO never ignores `aud`. Fixed: Q5
  now states this as resolved, no conditional branch.

A follow-on `loopctl verify-plan` run during this second pass caught one
self-inflicted regression: the first attempt at the Q3 fix cited
`minio_s3_bucket.bucket.id` from `storage.tf`, but that resource lives
inside `module.buckets` and is not addressable from outside the module.
Fixed: the new `storage.tf`-local policy scopes by bucket **name** (a
plain string), matching how the module's own policies build their ARNs.

Not yet re-verified by an agent: re-dispatch `loop-plan-reviewer` once more
before unblocking this ticket from `blocked`.
