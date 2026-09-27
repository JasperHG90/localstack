---
type: component
title: Vault's dynamic secrets engines
description: "The three engines that mint short-lived credentials: nomad and consul, whose mounts and management tokens Ansible owns while Terraform owns the roles, and the redis database engine, which Terraform owns end to end in database.tf. Says who reads each role and records the traps: lease TTL is a mount property, Redis users vanish on restart, and a max_ttl too short restarts the consumer."
tags: [vault, secrets-engines, nomad, consul, redis, database, terraform, ansible]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: machine-roles-tf
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: database-tf
    resource: git:3ec5d1e:deployments/infrastructure/database.tf
  - id: nomad-server-tasks
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/tasks/main.yml
  - id: enable-consul-secrets
    resource: git:3ec5d1e:bootstrap/playbooks/enable_consul_secrets.yml
  - id: broker-py
    resource: git:3ec5d1e:cli/src/localstack_cli/auth/broker.py
  - id: infrastructure-services-tf
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: F5-foundation-vault-nomad-secrets-engine
    resource: loop:F5-foundation-vault-nomad-secrets-engine
  - id: F6-foundation-vault-consul-secrets-engine
    resource: loop:F6-foundation-vault-consul-secrets-engine
  - id: S2-spike-postgres-vault-creds
    resource: loop:S2-spike-postgres-vault-creds
  - id: G2-nomad-ui-oidc-login
    resource: loop:G2-nomad-ui-oidc-login
---

# Vault's dynamic secrets engines

Three Vault engines mint short-lived credentials on this cluster: `nomad/`,
`consul/` and `redis/`. Besides these, jobs read static KV values and the
identity tokens described in
[the workload identity chain](/components/workload-identity-chain.md).
Postgres credentials still come from KV. Moving them to an engine was decided
in [ADR 0005](/decisions/0005-postgres-credentials-come-from-vaults-database-engine.md),
and the rollout ticket, R3, is blocked.

## Who owns what

| Engine | Mount and config | Roles | Upstream policy |
|---|---|---|---|
| `nomad/` | Ansible, `bootstrap/roles/nomad_server/tasks/main.yml` (`secrets enable`, `config/access` with the Nomad bootstrap token, `config/lease ttl=30m max_ttl=1h`) | Terraform, `machine_roles.tf` | Terraform (`nomad_acl_policy`, through `nomad.manage`) |
| `consul/` | Ansible, `bootstrap/playbooks/enable_consul_secrets.yml` (`secrets enable`, `config/access` with the Consul management token) | Terraform, `machine_roles.tf` | Ansible (`community.general.consul_policy`) |
| `redis/` | Terraform, `database.tf` | Terraform, `database.tf` | none, Redis ACL rules are inline |

The split follows one rule: a management token for Nomad or Consul never
reaches Terraform. Ansible reads them on the manager and writes them into
`config/access`, and Vault never returns them. F5 set this up for Nomad and
F6 copied it for Consul.

The two sides are not symmetric. Nomad ACL policies are Terraform's, written
through the aliased `nomad.manage` provider. The Consul `deploy` policy is
Ansible's, because provider 5.3.0 attaches a Consul policy to a role only by
name and cannot write its rules, so authoring it in Terraform would need the
management token. F6's plan had asked for both, Terraform owning the policy
and never holding the token. The provider schema made that impossible, and
the operator chose Ansible. F13's plan records that F11's first review
failed on assuming the two were symmetric.

## Roles and who reads them

| Path | Mints | Read by |
|---|---|---|
| `nomad/creds/deploy` | client token, `deploy` policy | `localstack login` for the operator, which becomes `NOMAD_TOKEN` for both roots |
| `nomad/creds/manage` | management token | `localstack login` for status commands, and `data.vault_nomad_access_token.manage` on every infrastructure plan |
| `nomad/creds/dash_read` | client token, `dash-read` policy | the dash job, through its `dash` JWT role |
| `consul/creds/deploy` | token, Ansible's `deploy` policy (TTL 30m, max 60m) | `localstack login`, exported by `localstack env` for the state backend and the applications root's provider |
| `redis/creds/cache-<job>` | a Redis ACL user limited to `~<job>:*` | the job named in `local.redis_cache_consumers`, `embark` today |

The operator reaches `nomad/creds/deploy`, `nomad/creds/manage` and
`consul/creds/deploy` through exact grants in the `developer` policy
(`identity.tf`). The field names differ per engine
(`secret_id` for Nomad, `token` for Consul), and `cli/src/localstack_cli/auth/broker.py`
is the one place that maps them. How Terraform consumes these is
[Terraform deployer credentials](/components/deployer-credentials.md). How a
job gets permission to read one is
[the workload identity chain](/components/workload-identity-chain.md).

## Traps in the Nomad and Consul engines

- **Lease TTL is a mount property for Nomad.** `vault_nomad_secret_role` takes
  no `ttl`, so the 30m/1h lease is set in Ansible. F5's plan assumed the
  role took one. The Consul role does take `ttl` and `max_ttl`.
- **`type` on a Nomad role is a writable field, not a ceiling.** G2 found
  that a second role with `type = "management"` mints what the ACL resources
  need, which removed a planned move to Ansible. It also means anyone who can
  write `nomad/role/*` can turn `deploy` into a management role. F13's plan
  review traced that route from `nomad/role/*` to the Vault root token.
- **Dynamic host volumes need namespace capabilities.** `host_volume "*"`
  governs mounting. Creating a volume needs `host-volume-*` in the namespace.
  F5's ticket had these confused, and a live review caught it.
- **Consul `session_prefix`.** State locking creates sessions. F6's first
  `session_prefix "terraform/"` granted nothing, because session rules match
  node names. The Ansible policy now uses `session_prefix ""`.
- **Management tokens pile up.** Every infrastructure plan mints a fresh
  `vault-manage-*` token and Terraform never revokes a data source's lease,
  so they live until they age out within the hour.

## The redis database engine

`database.tf` owns the mount, the connection and one role per consumer.
`machine_roles.tf` owns the matching policy and JWT role, keyed off the same
`local.redis_cache_consumers`. Adding a job there creates all three. One role
per job, not a shared `cache` role, is
[ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)
applied to Redis.

Order matters inside one apply:

- `vault_mount.redis` `depends_on` `vault_policy.developer`, because the
  operator's token needs the exact `sys/mounts/redis` grant first.
- The connection `depends_on` `nomad_job.redis` (which sets `detach = false`)
  and `null_resource.firewall`, because `verify_connection` dials Redis during
  apply.

Traps:

- **The mount is `redis`, not `database`.** S2's spike created a `database`
  mount from the applications root and kept it for later work. Its file was
  deleted in commit 19c1696, and that root's state may still track the mount,
  so reusing the path risks one root destroying the other's engine.
- **Redis users exist only in memory.** Any restart of the redis task wipes
  every minted user while Vault still holds valid leases. A renewal does not
  re-create them, because `renew_statements` is empty. The fix is restarting
  the consumer (`nomad job restart embark`) so it mints again. Until then
  embark serves uncached.
- **`max_ttl` decides restarts.** At `max_ttl` the template must mint a new
  user, the password changes, and embark's `change_mode = "restart"` fires.
  At 1h that was 17 restarts in 15 hours of a GPU service with a 25-second
  model load. It is 720h now, and the cost is the slow recovery above.
- **`+@connection` is required.** Without it clients fail on `PING`,
  `SELECT` and the connect handshake.
- **The firewall rule names the consumer's node.**
  `deployments/infrastructure/services.tf` allows 6379
  only from the embark node. A new consumer on another node cannot connect
  until its address is added there.

## What was proven but not built

S2 proved the Postgres path end to end on memex's real tables, including the
`SET ROLE` needed for revocation and what a pool does when its lease
expires. The findings and the runbook are the
[Postgres dynamic credentials proposal](/proposals/postgres-dynamic-credentials.md),
and the traps it hit are the
[write-only credentials practice](/practices/terraform-write-only-credentials.md).
