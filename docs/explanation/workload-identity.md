---
description: How a Nomad task's Workload Identity JWT becomes a scoped Vault token or SeaweedFS credential, and the conventions a new consumer follows.
stale_after: 2027-04-20
sources:
  - resource: bootstrap/roles/nomad_server/templates/nomad.hcl.j2
  - resource: bootstrap/roles/nomad_server/tasks/main.yml
  - resource: bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json
  - resource: bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2
  - resource: deployments/infrastructure/machine_roles.tf
  - resource: deployments/infrastructure/services/seaweedfs.hcl
  - resource: deployments/applications/storage.tf
  - resource: deployments/applications/services/memex/auth_oidc.json
  - resource: deployments/applications/services/openviking.hcl
  - resource: deployments/infrastructure/services.tf
---

# Nomad Workload Identity and the Vault JWT trust chain

Nomad issues a Workload Identity (WI) JWT to every task. Vault trusts that JWT
through the `jwt-nomad` auth mount and hands the task a scoped token. That is
the cluster's machine identity: the default path carries no static credential,
and every secret read is keyed on the job that asked for it. This page documents
the chain as it runs today, the ownership split between Ansible and Terraform,
and the convention downstream consumers (SeaweedFS STS, service bearer auth) follow
when they need their own audience.

## The chain, end to end

1. **Nomad issues a WI JWT per task.** The server config
   (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2`) sets
   `vault { default_identity { aud = ["vault.io"] ttl = "1h" } }`, so every
   task that declares a `vault {}` block gets a JWT with `aud = ["vault.io"]`
   and a 1h TTL.
2. **Vault trusts the issuer through `jwt-nomad`.** The Ansible role
   (`bootstrap/roles/nomad_server/tasks/main.yml`) enables the `jwt` auth
   method at path `jwt-nomad` and configures it to pull keys from Nomad's
   JWKS endpoint:

   ```
   jwks_url = "http://127.0.0.1:4646/.well-known/jwks.json"
   ```

   From outside a node, the same endpoint is
   `http://192.168.2.30:4646/.well-known/jwks.json`. Verify it returns a key
   set:

   ```
   curl -s "$NOMAD_ADDR/.well-known/jwks.json" | jq '.keys | length'
   ```

   SeaweedFS does not use this URL. It is configured with Nomad's issuer
   instead. See "Keyless SeaweedFS access" below.
3. **The `nomad-workloads` role maps claims to a policy.** The role
   (`bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`)
   binds `aud = ["vault.io"]`, takes `nomad_job_id` as the user claim, and
   maps three claims into Vault alias metadata: `nomad_namespace`,
   `nomad_job_id`, `nomad_task`. The token it mints carries the
   `nomad-workloads` policy.

Confirm the role live:

```
vault read -format=json auth/jwt-nomad/role/nomad-workloads | \
  jq '{bound_audiences: .data.bound_audiences, token_policies: .data.token_policies, claim_mappings: .data.claim_mappings}'
```

## The fixed-claims constraint

Vault's role maps exactly three claims, no others: `nomad_namespace`,
`nomad_job_id`, `nomad_task`. Nomad 2.0.4 (the version this cluster runs)
parses `extra_claims` in a task `identity` block, but the Vault role ignores
anything beyond those three, so per-job custom scoping through Vault is
unavailable in practice. Every policy path templates from `nomad_job_id` and
`nomad_namespace`. There is no way to grant a workload access keyed on a
custom claim without also editing `claim_mappings`.

Confirm it live:

```
vault read -format=json auth/jwt-nomad/role/nomad-workloads | jq '.data.claim_mappings'
```

## The shared `nomad-workloads` policy

The policy is in
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` and is
applied by Ansible. It is three `path` blocks:

- `read` on `secret/data/<namespace>/<job_id>/*` and the bare
  `secret/data/<namespace>/<job_id>` path. A task can read the **values** of
  secrets under its own job id only.
- `list` on `secret/metadata/<namespace>/*`. A task can enumerate the
  **paths** of every secret in its own Nomad namespace, not just its own
  job's.
- Zero `bootstrap/*` access. The policy grants nothing on the `bootstrap`
  mount.

### Threat model: narrowed, but not per-job

Secret **values** are job-scoped. Secret **paths** are not: the
`secret/metadata/<namespace>/*` list grant lets any workload enumerate every
path any other job in the same Nomad namespace has written. Nearly every job
on this cluster runs in the `default` namespace, so in practice that grant is
cluster-wide path enumeration. It does not leak values, only that a path
exists. The `bootstrap` mount is closed to workload tokens. So the policy is
per-job for values and per-namespace for paths, and calling it strictly
per-job would be false.

## The ownership split: Ansible root, Terraform per-job

The root of trust is in Ansible because it must exist before Terraform can
authenticate to Vault at all: the `jwt-nomad` mount, its JWKS config, the
default `nomad-workloads` role, and the shared policy are all created by
`bootstrap/roles/nomad_server/tasks/main.yml`.

Per-job roles and policies live in Terraform, beside the engine they grant
access to. The worked example is the ACME job:

- `deployments/infrastructure/machine_roles.tf` declares
  `vault_jwt_auth_backend_role.acme` and `vault_policy.acme_tls_write` on the
  Ansible-created `jwt-nomad` mount.
- `deployments/infrastructure/services/acme.hcl` selects the role with
  `vault { role = "${vault_role}" }`.

### The one-token rule

A Nomad task performs a single JWT login and holds a single Vault token, so
naming a dedicated role **replaces** `nomad-workloads` rather than adding to
it. A job that needs both a scoped grant and ordinary KV reads must list both
policies on its own role. That is why the `acme` role sets `token_policies` to
`["nomad-workloads", vault_policy.acme_tls_write.name]`: with only
`acme-tls-write` attached, the job could write its cert but could not read
the TransIP credential it needs to obtain one. `claim_mappings` must mirror
the shared role, or the `nomad-workloads` policy paths resolve to nothing
even when attached.

## The `identity`-stanza and audience convention

A task gets a Vault WI JWT one of two ways:

- **Implicit.** A bare `vault {}` block rides the server-side
  `default_identity` (`aud = ["vault.io"]`). No JWT is written to the alloc
  (`File: null`, `Env: null`), so the token cannot be captured or replayed.
  This is how memex and grafana read KV secrets, through
  `template { env = true }`. hermes rides the same default identity but
  names its own role with `vault { role = ... }`.
- **Explicit.** A named `identity` block overrides the default for that
  task. Use this when a consumer needs the raw JWT on disk or a different
  audience.

### The `name` field is load-bearing

An **unnamed** `identity {}` configures the task's default Nomad-API
identity, not the Vault one. It does not retarget Vault, it does not write a
JWT to disk, and it proves nothing a bare `vault {}` does not. The correct
override names the Vault identity:

```
identity {
  name        = "vault_default"
  aud         = ["vault.io"]
  file        = true
  change_mode = "noop"
}
```

(`noop`, not `restart`. This example writes a file, and Nomad restarts the
task on every renewal after the first, so `restart` buys nothing a
file-reading consumer needs. See "Prefer `change_mode = noop` for a file
identity" below.)

`vault_default` matches the server-side `default_identity` for the `default`
cluster. `file = true` writes the JWT to `secrets/nomad_vault_default.jwt`
inside the alloc, which a raw-JWT consumer reads. Confirmed live on Nomad
2.0.4: an unnamed block populates the task's singular default `Identity`
field, and a named block populates the `Identities` array. Only the named form
lands a JWT on disk.

### Pin the path with `filepath`, do not discover it

The default path is `secrets/nomad_<name>.jwt`, but do not depend on
deriving it. Set `filepath` and the jobspec states the path outright, so the
consumer's config and the file cannot drift apart:

```
identity {
  name        = "memex"
  aud         = ["memex"]
  file        = true
  filepath    = "secrets/nomad_memex.jwt"
  ttl         = "1h"
  change_mode = "noop"
}
```

`filepath` is alloc-relative. The in-container path gains a leading slash
(`/secrets/nomad_memex.jwt`).

### Prefer `change_mode = "noop"` for a file identity

Nomad restarts the task on **every** renewal after the first, with no test
for whether anything material changed. At `ttl = "1h"` that is an hourly
restart. A consumer that re-reads the file per request needs no restart, so
`noop` is the right default for `file = true`. The restart warning in
Nomad's own validation is scoped to `Env`, not `File`.

### Do not pin a token-reading task to a non-root user

Nomad skips the chown and leaves the JWT world-readable only when the task
sets no `user`. Adding `user =` to a task whose process runs unprivileged
breaks its ability to read its own identity file, and the failure is
silent if that consumer falls back to another credential.

### One audience per verifying service, never per job

`aud` identifies the **verifier** (Vault, SeaweedFS), not the client job. Per-job
distinction comes from `nomad_job_id`, which the policy templates on. Giving
each job its own audience would force every verifier to run a separate role
or provider per client, for no scoping gain.

- Keep `vault.io` for the existing Vault path. Renaming breaks every running
  workload at once.
- Add a distinct audience only per new consumer class that verifies tokens
  (for example `seaweedfs` for SeaweedFS STS, described in "Keyless
  SeaweedFS access" below).

Audience registry:

| `aud` | Verifier | Defined in |
|-------|----------|------------|
| `vault.io` | Vault, via the `jwt-nomad` mount | `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json` |
| `memex` | the memex server, against Nomad's JWKS | `deployments/applications/services/memex/auth_oidc.json` |
| `seaweedfs` | SeaweedFS STS, one role per job bound to `nomad_job_id` and `sub` | `deployments/infrastructure/services.tf` (`local.seaweedfs_iam`) |

`memex` is the first verifier that is not Vault: memex fetches Nomad's JWKS
itself and needs no Vault role. Per-job authorization is a `grant_rule` on
`nomad_job_id` in the memex server's own config, not a separate audience.

### File vs env token delivery

- **Env** (`template { env = true }`) is the default for Vault-templated
  secrets. The existing workloads all use it.
- **File** (`identity { file = true }`) is for consumers that read a raw JWT
  (SeaweedFS STS, service bearer auth). Both carry ephemeral credentials, and no
  static secret is reintroduced.

## Keyless SeaweedFS access

A Nomad job can use its bucket with no static S3 key: it trades its Workload
Identity JWT at SeaweedFS's STS for credentials that last an hour. Tempo, loki
and the OCI registry work this way.

Every other S3 client holds a static key that
`deployments/applications/storage.tf` mints. OpenViking reads one from
`default/openviking/seaweedfs` deliberately, because OpenViking's config layer
makes `access_key` and `secret_key` mandatory for an s3 backend and its S3
client drops the session token STS credentials require. See
`.okf/decisions/0007-openviking-static-key-has-no-claim-policy.md`. The
`backup-s3` and `restore-s3` jobs read static keys too. Tempo, loki and the
registry also have a static key under `default/<job>/seaweedfs`, kept as a
rollback path that their jobs do not read.

**What SeaweedFS trusts.** The `seaweedfs` job renders `secrets/iam.json` from
`local.seaweedfs_iam` in `deployments/infrastructure/services.tf`. It names
Nomad's issuer, `https://nomad.lab.orangecluster.nl`, as an OIDC provider with
client id `seaweedfs`, which is why a consumer's identity block must carry
`aud = ["seaweedfs"]`. The STS signing key comes from Vault at
`default/seaweedfs/sts`, and `defaultEffect` is `Deny`, so a request no policy
allows is refused.

**How access is decided.** Each entry in `local.seaweedfs_keyless_jobs` becomes
one role and one policy. The policy reaches only that job's bucket. The role's
trust policy requires the token's `nomad_job_id` to equal the job id and its
`sub` to match `global:default:<job>:*`. Nomad signs both claims, so a job
cannot assume another job's role, and the client must name the role it wants
by sending `RoleArn` and `RoleSessionName`. Keying off the job id rather than a
custom claim is deliberate: Vault's `nomad-workloads` role maps only three
claims (see "The fixed-claims constraint" above), and using the same key for
SeaweedFS keeps one scoping story across both verifiers.

SeaweedFS also has a claim mode, `policyClaim`, which applies the policy named
by a claim. The cluster does not use it, because it splits the claim on commas:
in a spike, a job named `evil,tempo` was given tempo's policy. The record is
`.okf/decisions/0017-seaweedfs-keyless-roles-bound-per-job.md`.

SeaweedFS reads `secrets/iam.json` only at start, so adding a keyless job
restarts it.

Giving a job keyless access is
[How to give a job keyless SeaweedFS access](../how-to/give-a-job-keyless-seaweedfs-access.md),
or, for a service built on aws-sdk-go v1,
[How to give an aws-sdk-go v1 service keyless SeaweedFS access](../how-to/give-an-aws-sdk-go-service-keyless-seaweedfs-access.md).
Proving the exchange by hand is
[How to exchange a workload JWT for SeaweedFS credentials](../how-to/exchange-a-workload-jwt-for-seaweedfs-credentials.md).

**Before SeaweedFS.** Until 2026-10-20 MinIO was the cluster's S3 store and
the verifier for audience `minio`. It ran in claim mode, applying the MinIO
policy whose name matched the token's `nomad_job_id`, and it carried a second
target with audience `minio-poc2` as a documented exception to the
one-audience-per-verifier rule. MinIO was end of life and its image no longer
downloaded, so every bucket moved to SeaweedFS and MinIO was removed the same
day, with both its audiences. The records are
`.okf/decisions/0016-seaweedfs-replaces-minio.md` and
`.okf/decisions/0018-remove-minio.md`.
