---
epic = "minio"
depends_on = ["F2-foundation-vault-oidc-provider", "A1-audit-plan-premise-sweep"]
priority = 10
summary = "Give humans tiered MinIO console access (Admin, Reader, Writer) via three Vault-gated OIDC providers on the MinIO job, each bound to a matching MinIO role policy. Spans both Terraform layers, so the cross-layer ordering constraint is the real cost."
tags = ["minio", "vault", "oidc", "terraform"]
---

# M2 — MinIO OIDC POC, human path (console login by tier)

## Title

Give humans tiered MinIO console access (Admin / Reader / Writer) via
three Vault-gated OIDC providers on the MinIO job, each bound to a
matching MinIO role policy.

## Size / Effort

**Medium.** Two Terraform layers change. The infrastructure layer gains
three `identity_openid` provider blocks in the MinIO job env template
(`deployments/infrastructure/services/minio.hcl`) plus new
`templatefile()` inputs. The applications layer gains three named MinIO
policies. Effort is driven by the cross-layer ordering constraint
(MinIO validates `role_policy` names at startup, and the policies live
in a different Terraform state than the job) and by threading the F2
OIDC client credentials into the job's Vault template.

## Triggered by

The localstack home-lab auth epic. Confirmed handoff: Vault is the OIDC
IdP for humans (Zitadel dropped). Humans need console access to MinIO
segmented by tier, gated so a reader cannot assume admin. This ticket
is the MinIO (relying-party) side of that design. It depends on F2,
which scaffolds the Vault OIDC provider, key, scope, per-tier clients,
group assignments, and Vault groups.

## Context

Today MinIO runs as a Nomad job with only root credentials and no OIDC:

- `deployments/infrastructure/services/minio.hcl:32-40` — the
  `template { env = true }` block that injects `MINIO_ROOT_USER`,
  `MINIO_ROOT_PASSWORD`, and `MINIO_PROMETHEUS_AUTH_TYPE`. This is the
  only place env is injected into the MinIO container, and it is where
  the three `MINIO_IDENTITY_OPENID_*_<tier>` variable sets must go.
- `deployments/infrastructure/services.tf:301-306` — the
  `nomad_job "minio"` resource renders the job with
  `templatefile(..., { minio_secret = ... })`. Any new templatefile
  input the job needs (for example OIDC config URLs or per-tier
  metadata) is added to this map.
- `deployments/infrastructure/services/minio.hcl:42-46` — the
  `minio-console` service on port 9001. The OIDC redirect URI targets
  this console.
- `deployments/applications/modules/bucket/main.tf:11-45` — the
  existing `minio_iam_policy` pattern (per-bucket read-write and
  read-only policies with `s3:*` and `s3:GetObject`/`s3:GetBucketLocation`
  statements). The three tier policies mirror this JSON shape but are
  cluster-wide, not scoped to one bucket.
- `deployments/applications/providers.tf:40-44` — the `minio` provider,
  authenticated with the root access/secret key pulled from the
  ephemeral Vault secret. This is the credential that lets the
  applications layer create the tier policies.
- `deployments/applications/services.tf:11-14` — the ephemeral
  `vault_kv_secret_v2 "minio_admin"` at `default/minio/localstack`
  feeding the provider above.

What is missing: no `identity_openid` provider is configured on the
job, and no admin/writer/reader MinIO policies exist for OIDC users to
assume via `role_policy`.

## Non-goals / out of scope

- The Vault side (F2): the OIDC provider, key, scope, the three
  per-tier `vault_identity_oidc_client` resources, the
  `vault_identity_oidc_assignment` group bindings, and the Vault groups
  (`minio-admins`, `minio-readers`, `minio-writers`). This ticket
  consumes those; it does not create them.
- The machine/service (STS `AssumeRoleWithWebIdentity` or access-key)
  path. This ticket is the human console-login path only.
- Any change to existing per-bucket policies in `modules/bucket/` or to
  the service-account users in `deployments/applications/storage.tf`.
- Per-bucket scoping of the tier policies. The POC grants cluster-wide
  tier access; bucket-scoped tiers are a later refinement.

## Requirements & restrictions

Must achieve:

1. Three `identity_openid:<tier>` providers on the MinIO job (admin,
   reader, writer), each with `role_policy` set to the matching MinIO
   policy name. Setting `role_policy` is what makes each a distinct
   role provider requiring its own client, which is the mechanism the
   design relies on for per-tier gating.
2. Three named MinIO policies: admin = full access; writer =
   put/get/list; reader = get/list.
3. The MinIO console shows one login button per provider (three
   buttons), and Vault group assignments (from F2) refuse cross-tier
   login.

Restrictions the repo enforces:

- **Secrets in Vault, never hardcoded** (CLAUDE.md "Key Conventions").
  The OIDC client secrets produced by F2 must reach the container
  through the job's Vault `template` block or a Vault-written KV path,
  not as literals in HCL.
- **Surgical changes** (CLAUDE.md section 3). Touch only the MinIO job
  env template, its `templatefile()` inputs, and a new policies
  definition. Do not restyle or refactor adjacent jobs or the bucket
  module.
- **Nomad HCL is formatted** by the `nomad-fmt` pre-commit hook
  (`.pre-commit-config.yaml:14-21`). New HCL in `minio.hcl` must pass
  `nomad fmt`.
- **Match existing style**: mirror the Vault templating idiom already
  in `minio.hcl:34-35` (`{{ with secret "..." }}{{ .Data.data.X }}{{ end }}`)
  for any secret the job reads.

## Code surface

- `deployments/infrastructure/services/minio.hcl:32-40` — extend the
  `template { env = true }` block with three provider variable sets.
  Each tier needs (MinIO env-var form, `<tier>` uppercased as the
  provider suffix):
  `MINIO_IDENTITY_OPENID_CONFIG_URL_<tier>`,
  `MINIO_IDENTITY_OPENID_CLIENT_ID_<tier>`,
  `MINIO_IDENTITY_OPENID_CLIENT_SECRET_<tier>`,
  `MINIO_IDENTITY_OPENID_ROLE_POLICY_<tier>`,
  `MINIO_IDENTITY_OPENID_DISPLAY_NAME_<tier>`,
  `MINIO_IDENTITY_OPENID_SCOPES_<tier>`,
  `MINIO_IDENTITY_OPENID_REDIRECT_URI_<tier>`. The client id/secret are
  read from the Vault path F2 writes (see Open Questions on where that
  path is). `ROLE_POLICY_<tier>` is the literal policy name created in
  the applications layer.
- `deployments/infrastructure/services.tf:301-306` — add any non-secret
  per-tier inputs (config URL, redirect URI, policy names, display
  names) to the `templatefile()` map so the job template can interpolate
  them. Follow the existing input-map convention used by the `grafana`
  job at `services.tf:333-355`.
- `deployments/applications/` — add a new file (suggest
  `minio_oidc_policies.tf`) defining three `minio_iam_policy` resources
  (admin/writer/reader) whose `name` values match the `role_policy`
  strings referenced by the job. Mirror the JSON statement shape in
  `deployments/applications/modules/bucket/main.tf:11-45`. Do not add
  these to `modules/bucket/`, which is per-bucket and instantiated with
  `for_each`; the tier policies are singletons.

## Tests & validation gates

### Repo gate (automated, offline)

- `just pre_commit` — runs `pre-commit run --all-files` (`justfile:17-18`).
  This gate is now Terraform-aware. Relevant hooks
  (`.pre-commit-config.yaml`): `check-yaml`, `check-json`,
  `end-of-file-fixer`, `detect-private-key`, `nomad-fmt`
  (`nomad fmt -recursive` over `*.hcl`, lines 16-21), and the two local
  Terraform hooks — `terraform-fmt` (`terraform fmt -check -recursive`,
  lines 22-27) and `terraform-validate` (`scripts/tf_validate.sh`, lines
  28-33). `tf_validate.sh` validates all three roots offline
  (`deployments/infrastructure`, `deployments/applications`,
  `deployments/applications/modules/bucket`) via `init -backend=false`,
  so both the new `minio_oidc_policies.tf` and the edited `minio.hcl` /
  `services.tf` are covered by `just pre_commit`. New HCL must be
  `nomad fmt` clean, new `.tf` must be `terraform fmt` clean and
  `validate`-clean, and neither may embed a private-key literal. There
  is no CI workflow; `just pre_commit` is the blessed pre-merge gate.

### Evals (live cluster, run after F2 is applied and the job redeployed)

The live cluster is reachable: `VAULT_ADDR`, `VAULT_TOKEN`,
`NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set in the
environment, and `mc`, `vault`, `nomad`, and `terraform` are on PATH.
The acceptance below is therefore runnable, not hypothetical. Every
step depends on F2 being applied (Vault provider/clients/assignments/
groups exist) and on this ticket's policies + job changes being applied
in the cross-state order from Open Question #2.

Set up the `mc` admin alias once from the root credentials in Vault (the
same secret the applications provider uses,
`default/minio/localstack`), then run the checks. Substitute the actual
tier policy names created in `minio_oidc_policies.tf` for
`minio-admin` / `minio-writer` / `minio-reader` below if they differ.

1. **Three OIDC role providers exist on MinIO with the right
   `role_policy`.**
   Command (per tier):
   `mc admin config get minio identity_openid:admin`
   (repeat for `identity_openid:writer`, `identity_openid:reader`).
   Expected: each returns a populated block whose `role_policy` equals
   the matching tier policy name (`minio-admin` / `minio-writer` /
   `minio-reader`), with a non-empty `config_url`, `client_id`, and
   `redirect_uri`. All three named configs must be present.

2. **The three tier policies exist with the expected action sets.**
   Command (per tier):
   `mc admin policy info minio minio-admin`
   (repeat for `minio-writer`, `minio-reader`).
   Expected: `minio-admin` grants full access (`s3:*` / `admin:*` per
   the brief); `minio-writer` grants put/get/list (plus the multipart
   actions from Open Question #5 if the operator accepts them);
   `minio-reader` grants get/list only and no `s3:PutObject`. A
   non-zero exit or "policy does not exist" fails the step.

3. **The three Vault OIDC clients and their per-tier assignments
   exist.**
   Command (per tier):
   `vault read identity/oidc/client/<tier>` and
   `vault read identity/oidc/assignment/<tier-assignment>`.
   Expected: each `client` read returns a `client_id`, `redirect_uris`
   matching the console redirect URI wired into the job, and an
   `assignments` list referencing the tier's assignment; each
   `assignment` read lists exactly the intended Vault group
   (`minio-admins` / `minio-writers` / `minio-readers`) in its
   `group_ids` / `entity_ids`. A tier whose assignment omits its group,
   or includes another tier's group, fails the step.

4. **Scripted cross-tier denial (the part that can be scripted).**
   Using a Vault entity that is a member of `minio-readers` only,
   exercise the Vault OIDC authorize endpoint for both the reader and
   admin clients:
   - Reader client (should succeed):
     `vault read identity/oidc/provider/<provider>/authorize \
       client_id=<reader-client-id> scope="openid <scope>" \
       redirect_uri=<reader-redirect-uri> response_type=code \
       state=<s> nonce=<n>`
     Expected: returns an authorization `code` (the reader entity is in
     the reader client's assignment).
   - Admin client, same reader entity (should be refused):
     `vault read identity/oidc/provider/<provider>/authorize \
       client_id=<admin-client-id> scope="openid <scope>" \
       redirect_uri=<admin-redirect-uri> response_type=code \
       state=<s> nonce=<n>`
     Expected: refused — no `code`; the endpoint returns
     `access_denied` (the reader entity is not in the admin client's
     assignment). This scripts the assignment-level gating that backs
     the browser refusal in step 5.

5. **Residual manual browser check (close-out acceptance — cannot be
   scripted).**
   In a browser against the MinIO console (port 9001,
   `minio.hcl:42-46`):
   - a `minio-readers` member clicks the **Reader** login button,
     authenticates, and has read-only S3 access (list/get succeed,
     put/upload is denied);
   - the same user clicks the **Admin** login button and is refused at
     the Vault consent/authorize step;
   - a `minio-admins` member clicks the **Admin** button and has full
     access.
   Expected: three login buttons render, reader is read-only, reader is
   refused on admin, admin has full access. This is the genuinely
   browser-driven acceptance; record its result in the ticket's
   acceptance notes.

Steps 1-4 are runnable now (given F2 applied); step 5 is the manual
residual. All five depend on F2 being applied and the MinIO job
redeployed with the new providers.

**Eval marker:** the scenarios above are encoded as a five-column eval
table at `.loop/evals/M2-minio-poc-human-tiers.md` (six rows: the three
deterministic `mc`/`vault` checks, the scripted reader read-only judgment
row, the cross-tier-deny guardrail, and the human-scored manual browser
close-out). All rows depend on F2 being applied and the MinIO job
redeployed.

## Risk assessment

- **Blast radius:** the MinIO job restarts when the env template
  changes (`deployments/infrastructure/services/minio.hcl`), briefly
  interrupting S3 for every dependent service (Loki, MLflow, memex,
  DuckLake). A malformed `identity_openid` env set can make MinIO fail
  to start.
- **Cross-layer ordering (likeliest failure):** MinIO validates each
  `role_policy` name at startup. The policies are created in the
  applications Terraform state, but the job with `ROLE_POLICY_<tier>`
  lives in the infrastructure state. If the job reloads before the
  policies exist, the OIDC provider config is rejected and login fails
  (or the job crash-loops). The policies must be applied first. See
  Open Questions.
- **Reversibility:** high. Removing the three env sets and reverting the
  `templatefile()` inputs restores the prior job. The three policies are
  deletable. No data migration.
- **Secret handling:** if the OIDC client secret is threaded as a
  `templatefile()` literal instead of via the Vault template block, it
  lands in Nomad job JSON in plaintext and may trip `detect-private-key`
  or violate the secrets-in-Vault convention. Read it from Vault.

## Subtickets

1. **Define the three MinIO tier policies** (applications layer). Add
   `minio_oidc_policies.tf` with admin/writer/reader `minio_iam_policy`
   resources; `terraform validate` and `just pre_commit` pass. No job
   dependency yet. (Depends on: nothing in this ticket.)
2. **Add the three `identity_openid` provider env sets** to
   `minio.hcl` and the matching `templatefile()` inputs in
   `services.tf`, referencing the F2 Vault paths/attributes and the
   policy names from subticket 1. `nomad fmt` clean. (Depends on: 1,
   and F2 for the client credentials.)
3. **Wire the ordering** so the policies (subticket 1) are applied
   before the MinIO job reloads with `role_policy`. Resolve the
   cross-state dependency (see Open Questions #2). (Depends on: 1, 2.)
4. **Acceptance** against the live cluster: run the scripted evals
   (steps 1-4) and the manual browser check (step 5), and record the
   reader-refused-by-admin result. (Depends on: 1-3 and F2 applied.)

## Open questions

1. **Where do the F2 client id/secret reach the job?** F2's
   `vault_identity_oidc_client` exposes `client_id`/`client_secret` as
   Terraform attributes in the infrastructure (or a separate) state.
   The job currently reads secrets from Vault KV at
   `${minio_secret}` paths via its template block
   (`minio.hcl:34-35`). Fork: (a) F2 writes each tier's client
   credentials to a KV path such as `default/minio/oidc/<tier>` and the
   job reads them with `{{ with secret ... }}`, or (b) the credentials
   are passed as `templatefile()` variables from the F2 resource
   attributes. **Recommendation: (a).** It matches the existing idiom,
   keeps the secret out of rendered job JSON, and satisfies the
   secrets-in-Vault convention. Requires F2 to expose those KV paths;
   flag as an F2 interface requirement.

2. **How is the cross-state ordering enforced?** The policies are in
   the applications state; the job is in the infrastructure state.
   There is no `depends_on` across states. Fork: (a) document a
   manual apply order (policies then job) in the ticket and runbook,
   (b) move the three tier policies into the infrastructure state so a
   single `terraform apply` orders them via `depends_on` before
   `nomad_job.minio`, or (c) create the policies in the same layer as
   the job. **Recommendation: (b)** if the infrastructure layer can
   reach the MinIO provider; otherwise (a) for the POC. Note that the
   `minio` provider is currently only configured in the applications
   layer (`deployments/applications/providers.tf:40-44`), so (b)
   requires adding a MinIO provider there. Operator decides whether to
   duplicate the provider or accept manual ordering for the POC.

3. **Config URL value.** `MINIO_IDENTITY_OPENID_CONFIG_URL_<tier>` must
   point at the Vault OIDC provider's `.well-known/openid-configuration`
   endpoint from F2. The exact issuer URL is an F2 output. Confirm F2
   exposes it (as a TF output or KV entry) so subticket 2 can consume
   it. **Recommendation:** treat the issuer URL as an F2-provided input;
   do not hardcode it.

4. **Redirect URI host.** The console is reachable on port 9001
   (`minio.hcl:44`) but external access is fronted by HAProxy. Fork:
   redirect to the direct node address (`192.168.2.29:9001`) or the
   HAProxy-fronted hostname. **Recommendation:** use whatever host the
   F2 client's allowed redirect URIs are registered with; they must
   match exactly. Confirm against F2's client `redirect_uris`.

5. **Writer policy action set.** The brief says writer = put/get/list.
   Confirm whether writer should also include multipart and delete
   actions (`s3:AbortMultipartUpload`, `s3:DeleteObject`) needed for
   normal console uploads/overwrites, or strictly put/get/list.
   **Recommendation:** include the multipart actions required for
   console uploads to actually work, but exclude `s3:DeleteObject`
   unless the operator wants writers to delete. Flag for the operator.

## Resolved forks (operator, 2026-07-23)

- **Q1 → KV path `default/minio/oidc/<tier>`.** F2 writes each tier's
  client creds there; the job reads them with `{{ with secret ... }}`.
  Flag as an F2 interface requirement.
- **Q2 → Rely on the existing infra→applications apply order (documented).**
  The three tier policies (`admin`/`writer`/`reader`) are MinIO IAM
  policies created by the MinIO provider in the applications layer; the
  MinIO server job is in the infrastructure layer. MinIO IAM policies can
  only be created against a running MinIO, and the repo already applies
  infrastructure before applications — so server-up-then-policies is the
  natural, existing order. No cross-state `depends_on`, no moving
  policies, no duplicating the MinIO provider for the POC. Document the
  order in the runbook.
- **Q3 → Issuer/config URL is an F2-provided input.** Consume F2's
  `.well-known/openid-configuration` issuer (TF output or KV entry); do
  not hardcode it.
- **Q4 → HAProxy hostname `https://minio.localstack/oauth_callback`.**
  Must match F2's registered `redirect_uris` exactly; consistent with
  F2's https issuer.
- **Q5 → writer = put/get/list + multipart + delete.** Full write
  including `s3:DeleteObject`. (reader = get/list; admin = full.)

**Dependencies:** M2 depends on **F2** (OIDC provider/clients) and on
**F4** (network-wide `.localstack` DNS) — M2 must not be marked done until
F4 lands, so the MinIO console resolves from non-Mac LAN devices, not just
via the operator's `/etc/hosts`.
