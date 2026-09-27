---
type: component
title: memex, staged off the cluster
description: "memex's Nomad job has been commented out since 2026-09-04 to give the Jetson to embark, while its Vault OIDC clients, keys, groups, database, bucket, secrets and edge route stay declared in Terraform. Covers how its two OIDC trust paths (workloads and humans) are wired and what has to change before the job can come back."
tags: [memex, oidc, vault, nomad, workload-identity, postgres, staged]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: memex-jobspec
    resource: git:3ec5d1e:deployments/applications/services/memex.hcl
  - id: memex-auth-oidc
    resource: git:3ec5d1e:deployments/applications/services/memex/auth_oidc.json
  - id: memex-auth-keys
    resource: git:3ec5d1e:deployments/applications/services/memex/auth_keys.json
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: app-database
    resource: git:3ec5d1e:deployments/applications/database.tf
  - id: infra-oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: infra-identity
    resource: git:3ec5d1e:deployments/infrastructure/identity.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: haproxy
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: embark-commit
    resource: git:db51630
  - id: R5-rollout-memex-oidc-auth
    resource: loop:R5-rollout-memex-oidc-auth
  - id: R6-rollout-memex-human-oidc
    resource: loop:R6-rollout-memex-human-oidc
---

# memex, staged off the cluster

memex is not running. `db51630` (2026-09-04) commented out
`nomad_job.memex` in `deployments/applications/services.tf` to free
jetson-orin-nano for embark: embark needs the GPU there, and memex's ~6.5 GB
does not fit beside it. The comment above the block calls it "staged, not
dead". Everything memex depends on is still declared in Terraform, so
this page is mostly about what a person bringing it back has to get
right. Hermes used to be its main caller and now uses OpenViking instead ([Hermes](/components/hermes.md)).

## What is still declared

| Piece | Where |
|---|---|
| Jobspec, ready to render | `deployments/applications/services/memex.hcl` |
| API keys and OIDC config, as plain JSON | `deployments/applications/services/memex/auth_keys.json`, `auth_oidc.json` |
| `local.memex_auth_keys`, `local.memex_auth_oidc`, and the `memex_auth_oidc_shape_check` output | `deployments/applications/services.tf` |
| `data.vault_identity_oidc_client_creds.memex` (reads the human client's id by name) | `deployments/applications/services.tf` |
| Postgres role and database `memex`, with the `vector` extension | `deployments/applications/database.tf` |
| MinIO bucket `memex` and its writer key | `deployments/applications/storage.tf` |
| KV `default/memex/{postgres,minio,auth,bifrost}` | `deployments/applications/secrets.tf` |
| `bifrost_virtual_key.memex` | `deployments/applications/services.tf` |
| `vault_identity_oidc_key.memex_human`, `vault_identity_oidc_assignment.memex`, `vault_identity_oidc_client.memex` | `deployments/infrastructure/oidc.tf` |
| Groups `app-memex-admins`, `app-memex-readers` in `local.app_user_groups` | `deployments/infrastructure/identity.tf` |
| Host volume `memex_data`, constrained to jetson-orin-nano | `deployments/infrastructure/services.tf` |
| Edge route `memex.lab.orangecluster.nl` to 192.168.2.46:8000 | `deployments/infrastructure/services/haproxy.hcl` |

Its Redis consumer entry (`deployments/infrastructure/database.tf`) and its
firewall entry are commented out or gone. The daily MinIO backup moved from
the `memex` bucket to `openviking` (ticket `backup-swap-memex-for-openviking`).

## Two OIDC trust paths

memex trusts two issuers and picks one by the token's `iss`. Both are in
`auth_oidc.json`, whose `{{...}}` placeholders Terraform fills from
`local.memex_auth_oidc_substitutions`.

**Workloads (R5).** Issuer is Nomad's (`local.nomad_oidc_issuer`), audience
the literal `memex`, grants keyed on `nomad_job_id`. The issuer string must
match what Nomad advertises byte for byte, or provider selection fails. How
Nomad came to publish a discovery document is
[Nomad's OIDC discovery document](/components/nomad-oidc-discovery.md).

**Humans (R6).** Issuer is Vault's `lab` provider, and the audience is the
memex CLIENT ID, not `memex`. Vault signs only the ID token and hands back an
opaque batch token as the access token, so the memex client sends the ID
token (`credential: id_token`, memex v1.2.0 and later), whose `aud` is the
client id. R5 found this mismatch and split the human half out. R6 closed it
once memex 1.2.0 shipped mid-ticket.

The human client in `oidc.tf` has its own key, `memex-human` (7-day
rotation, 30-day verification), and both token TTLs at 30 days. Why a
dedicated key and a long access-token TTL are needed is
`docs/explanation/vault-oidc-tokens.md`. `client_type` and `key` are
immutable, so changing either means a new client id and a matching edit to
`auth_oidc.json`'s audience. R6's reflection records that the first answer to
"a month-long session" was "impossible", from treating a per-client field as
shared.

Dropping `memex` from `local.oidc_provider_client_ids` unpublishes that key
ring, so no memex human token verifies until the client is added back. That
works only because memex is the sole client on the key. Rotating
`memex-human` ends no token, because the old public key stays
published for the verification TTL (`oidc.tf`, corrected in `6c51b39`).
`docs/how-to/revoke-memex-human-tokens.md` still says a rotation reaches
tokens issued since the last one.

## Invariants and what enforces them

- **JSON syntax** in both files: `jsondecode` in `services.tf` fails the plan.
- **Grant-rule field names**: the `memex_auth_oidc_shape_check` output's
  precondition refuses any key outside `claim, value, policy, vault_ids,
  read_vault_ids`. memex ignores unknown keys, and a rule without `vault_ids`
  covers every vault, so a typo like `vault_id` would silently widen a grant.
- **Grant-rule order**: memex takes the first match. `app-memex-admins` must
  stay above `app-memex-readers`, or a person in both is downgraded. Nothing
  enforces this. The V5 check in `docs/how-to/verify-memex-oidc.md` tests it
  by hand.
- **Group names across roots**: the `value`s in `auth_oidc.json` must match
  keys of `local.app_user_groups` in the infrastructure root. Nothing
  enforces this.
- **Placeholders only in `issuer` and `audience`**: substitution runs over
  those two fields alone. A `{{...}}` anywhere else reaches Nomad's template
  engine unresolved.
- **No template action in a `#` line of the jobspec's env template**: that
  heredoc is consul-template source, so a `#` line is plain text and a
  double-brace action in it is parsed.

## Before the job comes back

The comment above the commented block says to change `memex_host` first.
That is not enough, and no ticket has exercised it:

1. **Placement is hard-coded in three places.** `memex.hcl` constrains the
   group to the literal `jetson-orin-nano`, `memex_host` is only the service
   address, and the `memex_data` volume is constrained to the Jetson. The
   image (`memex-jetson`), the CUDA and cuDNN mounts and the `seccomp`
   override are Jetson-specific too.
2. **`auth_keys.json` names a key Terraform does not write.** Its third
   entry reads `writer_key_vault_meetings`, and `vault_kv_secret_v2.memex_auth_keys`
   holds only `admin_key` and `writer_key`. Go templates render a missing map
   key as `<no value>`, so that entry would carry the fixed, guessable string
   `<no value>` as a scoped writer key. Not measured. Add the key to
   the secret or remove the entry.
3. **The `hermes` grant is dead.** `auth_oidc.json` still gives
   `nomad_job_id = hermes` unscoped `admin`, kept deliberately in R5 (plan
   Q3). Hermes no longer carries a memex identity, so the rule matches
   nothing today, and would give admin to any future job named `hermes`.
   `leo-consumer`'s `writer` grant is the only one with a known caller.
4. **Firewall.** `local.firewall_rules` has no memex entry. Its old LAN-wide
   rule on port 8000 outlived the job by a fortnight and silently widened
   embark's narrower rules on the same port (`services.tf`, comment above
   `null_resource.firewall`). A new entry should name its callers.
5. **The edge route points at embark's port.** `backend memex` still sends
   `memex.lab` to 192.168.2.46:8000, where embark now listens. embark's rules
   do not admit HAProxy (.30), so the route should fail its health check and
   answer 503. That holds only if no wider rule survives on the node. Not
   measured.

The Postgres credentials are still the static `default/memex/postgres` pair.
Ticket R7 (ready) plans to move memex to Vault-minted users per
[ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md)
and [ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md).
What that looks like against memex's tables is
[Short-lived Postgres credentials from Vault](/proposals/postgres-dynamic-credentials.md).

## Related

- [Vault's OIDC provider and its clients](/components/vault-oidc-provider.md)
- [embark, the embedding and rerank server](/components/embark.md), which holds the Jetson now
- [The host firewall](/components/host-firewall.md)

- `docs/how-to/verify-memex-oidc.md`, the V1 to V5 checks for both paths
- `docs/explanation/vault-oidc-tokens.md`, why the ID token and not the access
  token
- `docs/how-to/log-in-to-memex-from-a-laptop.md`
- `docs/explanation/workload-identity.md`
