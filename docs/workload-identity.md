# Nomad Workload Identity and the Vault JWT trust chain

Nomad issues a Workload Identity (WI) JWT to every task. Vault trusts that JWT
through the `jwt-nomad` auth mount and hands the task a scoped token. That is
the cluster's machine identity: no static credentials reach a workload, and
every secret read is keyed on the job that asked for it. This page documents
the chain as it runs today, the ownership split between Ansible and Terraform,
and the convention downstream consumers (MinIO STS in M1, service bearer auth)
follow when they need their own audience.

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

   MinIO does NOT consume this URL. Its `identity_openid` takes a discovery
   document, not a bare JWKS, and the pinned release strips `jwks_url`
   outright. See "Keyless MinIO access" below for the URL it does use.
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

The policy lives in `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
and is applied by Ansible. As of F9 (2026-07-30) it is three `path` blocks:

- `read` on `secret/data/<namespace>/<job_id>/*` and the bare
  `secret/data/<namespace>/<job_id>` path. A task can read the **values** of
  secrets under its own job id only.
- `list` on `secret/metadata/<namespace>/*`. A task can enumerate the
  **paths** of every secret in its own Nomad namespace, not just its own
  job's.
- Zero `bootstrap/*` access. F9 removed the prior `bootstrap/data/*`
  read/create/update and `bootstrap/metadata/*` list grants.

### Threat model: narrowed, but not per-job

Secret **values** are job-scoped. Secret **paths** are not: the
`secret/metadata/<namespace>/*` list grant lets any workload enumerate every
path any other job in the same Nomad namespace has written. Nearly every job
on this cluster runs in the `default` namespace, so in practice that grant is
cluster-wide path enumeration. It does not leak values, only that a path
exists. The `bootstrap` mount is closed to workload tokens. Describing this
policy as strictly per-job scoped would ship a false claim; the doc records
both halves.

## The ownership split: Ansible root, Terraform per-job

The root of trust lives in Ansible because it must exist before Terraform can
authenticate to Vault at all: the `jwt-nomad` mount, its JWKS config, the
default `nomad-workloads` role, and the shared policy are all created by
`bootstrap/roles/nomad_server/tasks/main.yml`.

Per-job roles and policies live in Terraform, beside the engine they grant
access to. The worked example is the ACME job:

- `deployments/infrastructure/acme.tf` declares
  `vault_jwt_auth_backend_role.acme` and `vault_policy.acme_tls_write` on the
  Ansible-created `jwt-nomad` mount.
- `deployments/infrastructure/services/acme.hcl` selects the role with
  `vault { role = "${vault_role}" }`.

### The one-token rule

A Nomad task performs a single JWT login and holds a single Vault token, so
naming a dedicated role **replaces** `nomad-workloads` rather than adding to
it. A job that needs both a scoped grant and ordinary KV reads must list both
policies on its own role. That is why `acme.tf` sets `token_policies` to
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
  This is how every current workload (minio, memex, hermes, grafana) reads
  KV secrets, through `template { env = true }`.
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
field; a named block populates the `Identities` array. Only the named form
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

`filepath` is alloc-relative; the in-container path gains a leading slash
(`/secrets/nomad_memex.jwt`).

### Prefer `change_mode = "noop"` for a file identity

Nomad restarts the task on **every** renewal after the first, with no test
for whether anything material changed. At `ttl = "1h"` that is an hourly
restart. A consumer that re-reads the file per request needs no restart, so
`noop` is the right default for `file = true`; the restart warning in
Nomad's own validation is scoped to `Env`, not `File`.

### Do not pin a token-reading task to a non-root user

Nomad skips the chown and leaves the JWT world-readable only when the task
sets no `user`. Adding `user =` to a task whose process runs unprivileged
breaks its ability to read its own identity file — and the failure is
silent if that consumer falls back to another credential.

### One audience per verifying service, never per job

`aud` identifies the **verifier** (Vault, MinIO), not the client job. Per-job
distinction comes from `nomad_job_id`, which the policy templates on. Giving
each job its own audience would force every verifier to run a separate role
or provider per client, for no scoping gain.

- Keep `vault.io` for the existing Vault path. Renaming breaks every running
  workload at once.
- Add a distinct audience only per new consumer class that verifies tokens
  (for example `minio` for MinIO STS). M1 has since added that one; see
  "Keyless MinIO access" below.

Audience registry:

| `aud` | Verifier | Owner |
|-------|----------|-------|
| `vault.io` | Vault, via the `jwt-nomad` mount | F1 |
| `memex` | the memex server, against Nomad's JWKS | R5 |
| `minio` | MinIO STS, `NOMAD` target | M1 |
| `minio-poc2` | MinIO STS, `POC2` target | M1, replace in the human ticket |

The last two rows share a verifier, which the rule above forbids. They are
the documented exception, not a precedent: MinIO refuses more than one
claim-mode target, so proving it can serve a second identity provider at all
requires a second target with its own client id, and a client id is matched
against `aud`. Nothing else may add an audience to a verifier it already has.
See "Keyless MinIO access" below.

`memex` is the first verifier that is not Vault: memex fetches Nomad's JWKS
itself and needs no Vault role. Per-job authorization is a `grant_rule` on
`nomad_job_id` in the memex server's own config, not a separate audience.

### File vs env token delivery

- **Env** (`template { env = true }`) is the default for Vault-templated
  secrets. The existing workloads all use it.
- **File** (`identity { file = true }`) is for consumers that read a raw JWT
  (MinIO STS, service bearer auth). Both carry ephemeral credentials; no
  static secret is reintroduced.

## What F1 delivers for M1, and what it does not

F1 delivered the **JWKS URL** (`http://192.168.2.30:4646/.well-known/jwks.json`)
and nothing more. Its scope was JWKS only; it did not deliver an OIDC
discovery document, which is what MinIO actually needs, so M1 could not
proceed on F1 alone.

**F10 has since enabled discovery**, so the rest of this section describes
history, not current state. Nomad now serves a discovery document at the
configured issuer:

```
curl -sk https://nomad.lab.orangecluster.nl/.well-known/openid-configuration
{"issuer":"https://nomad.lab.orangecluster.nl",
 "jwks_uri":"https://nomad.lab.orangecluster.nl/.well-known/jwks.json",
 "id_token_signing_alg_values_supported":["RS256","EdDSA"], ...}
```

MinIO's `identity_openid` consumes a discovery document
(`MINIO_IDENTITY_OPENID_CONFIG_URL`), not a bare JWKS, which is why it had to
wait. Enabling discovery meant setting `server { oidc_issuer = ... }` in the
Nomad server config and restarting the single Nomad server; that was
`F10-foundation-nomad-oidc-issuer`, and it is done. A verifier that needs
discovery (memex in R5, MinIO in M1) can now point at the issuer directly.

## Keyless MinIO access

M1 landed this. A Nomad job can now read its bucket with no static S3 key: it
trades its Workload Identity JWT for short-lived MinIO credentials. The
static keys in `deployments/applications/storage.tf` still exist and still
work, and no existing consumer was moved off them. Moving them is a separate
piece of work.

**What MinIO trusts.** Three env vars on the MinIO job
(`deployments/infrastructure/services/minio.hcl`) define the `NOMAD` target:

```
MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD=https://nomad.lab.orangecluster.nl/.well-known/openid-configuration
MINIO_IDENTITY_OPENID_CLIENT_ID_NOMAD=minio
MINIO_IDENTITY_OPENID_CLAIM_NAME_NOMAD=nomad_job_id
```

The config URL is the discovery document F10 turned on, not a bare JWKS: the
pinned release removed `jwks_url`. The client id is why a consumer's identity
block must carry `aud = ["minio"]`, because MinIO validates the audience
against it in every mode. The trailing `_NOMAD` names the target and MinIO
reads it verbatim, so the target is `NOMAD` and never `nomad`.

**How access is decided.** `claim_name = nomad_job_id` tells MinIO to apply
the policy whose NAME matches the JWT's `nomad_job_id` claim. So a job called
`foo` gets the MinIO policy called `foo`, and nothing else. Keying off the
job id rather than a custom claim is deliberate: Vault's `nomad-workloads`
role maps only three claims (see "The fixed-claims constraint" above), and
using the same key for MinIO keeps one scoping story across both verifiers.

**To give a new job keyless access**, two things must line up. Note that
NOTHING in this repo currently does, because M1 proved the mechanism with a
throwaway job and policy and then removed both. The first real consumer is
the one that creates these:

1. The job carries a named identity for the `minio` audience, per the
   convention above:

   ```
   identity {
     name        = "minio"
     aud         = ["minio"]
     file        = true
     filepath    = "secrets/nomad_minio.jwt"
     ttl         = "1h"
     change_mode = "noop"
   }
   ```

2. A `minio_iam_policy` exists whose `name` is exactly the job id, scoped to
   that job's bucket. Without it the exchange itself fails, before any
   credential is minted, with `None of the given policies are defined`. It
   does not hand back a credential that is then denied, so a job that cannot
   get credentials at all is the symptom of a missing policy.

The job then exchanges the JWT itself. The request carries its parameters in
the query string and needs no SDK, so `curl` is enough:

```
curl -sS -X POST "http://<minio>:9000/?Action=AssumeRoleWithWebIdentity\
&Version=2011-06-15&WebIdentityToken=$(cat /secrets/nomad_minio.jwt)"
```

It returns XML holding an `<AccessKeyId>`, `<SecretAccessKey>`,
`<SessionToken>` and an `<Expiration>` one hour out. `mc` takes all three in
one URL:

```
MC_HOST_sts="http://<AccessKeyId>:<SecretAccessKey>:<SessionToken>@<minio>:9000"
mc ls sts/<bucket>
```

**A second target already exists.** `POC2` (`aud = minio-poc2`) is configured
alongside `NOMAD`, on the same discovery document under a different client
id, and proves MinIO can hold two IdPs at once for the human-access work.
Its `role_policy` names `poc2-intentionally-undefined`, a policy that does
not exist and must not be created. MinIO's only principal check is `aud`
matching `client_id`, and any jobspec author chooses their own `aud`, so a
real policy here would grant that bucket to anyone who asked for the
audience. Pointing at nothing costs nothing at startup and fails per
request, which is what keeps the target safe to leave standing. Whoever
wires Vault in should REPLACE it rather than add a third target.

**Two MinIO behaviors worth knowing before editing its config.** Only one
provider may run in claim mode. A token arriving with no `RoleArn` has to
resolve to exactly one, so every other provider needs a `role_policy`, which
is why `POC2` carries one and `NOMAD` does not. And `LookupConfig` aborts the
WHOLE OIDC config load, every provider, if any
one provider's discovery document fails to parse, so pointing a new provider
at a URL that is not live takes down the working ones with it.

## Operator verification (run on the live cluster)

This proves the chain end to end. It writes a throwaway probe secret, runs a
scratch job that reads it keylessly, captures the WI JWT, and checks the
positive and negative policy results. Purge the secret and stop the job
afterward so nothing is left running.

### Pre-apply: the trust chain exists

```
# JWKS reachable (>= 1 key)
curl -s "$NOMAD_ADDR/.well-known/jwks.json" | jq '.keys | length'

# jwt-nomad auth method exists
vault auth list -format=json | jq -e '."jwt-nomad/"'

# role binds the expected audience and policy
vault read -format=json auth/jwt-nomad/role/nomad-workloads | \
  jq '{bound_audiences: .data.bound_audiences, token_policies: .data.token_policies}'
```

### At-close: keyless read end to end

Write the probe secret by hand (operator token; no Terraform state):

```
vault kv put -mount=secret default/wi-test/probe \
  key=wi-test-value nonce=probe
```

Run the scratch job (`tests/wi-vault-probe.nomad.hcl`):

```
nomad job run tests/wi-vault-probe.nomad.hcl
nomad job status -short wi-test      # status: running
```

The job prints the WI JWT, the rendered probe secret, and its byte count to
stdout (the secret files under `secrets/` are read-protected, so read them
through `nomad alloc logs`, not `nomad alloc fs`):

```
alloc=$(nomad job allocations wi-test | awk 'NR==2{print $1}')
nomad alloc logs "$alloc" probe
```

Expected: `---JWT---` is a non-empty `eyJ...` string; `---PROBE-LEN---` is
non-zero; `---PROBE---` shows `PROBE_KEY=wi-test-value` and
`PROBE_NONCE=probe`. The non-empty probe proves the keyless read succeeded.

Prove the login leg directly with the captured JWT:

```
jwt=$(nomad alloc logs "$alloc" probe | awk '/^eyJ/{print; exit}')
vault write -format=json auth/jwt-nomad/login role=nomad-workloads jwt="$jwt" | \
  jq '.auth.policies'
```

Expected: `policies` includes `nomad-workloads`.

### Negative cases: the real blast radius

Using the WI token minted above:

```
witoken=$(vault write -format=json auth/jwt-nomad/login \
  role=nomad-workloads jwt="$jwt" | jq -r '.auth.client_token')

# Another job's secret VALUE is denied
VAULT_TOKEN="$witoken" vault kv get -mount=secret default/other-job/probe
# -> Code: 403, permission denied

# The bootstrap mount is closed to workload tokens
VAULT_TOKEN="$witoken" vault kv get -mount=bootstrap github
# -> Code: 403, permission denied

# But another job's secret PATH is enumerable (namespace-wide list survives)
VAULT_TOKEN="$witoken" vault kv list -mount=secret default
# -> exit 0, lists every job's path in the default namespace
```

The first two are the narrowed policy working. The third is the surviving
gap: any workload in the `default` namespace can enumerate every other job's
secret paths (not values).

### Teardown

```
nomad job stop -purge wi-test
vault kv metadata delete -mount=secret default/wi-test/probe
```
