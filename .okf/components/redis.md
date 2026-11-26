---
type: component
title: Redis cache
description: "A memory-only Redis on radxa whose callers get a per-job ACL user minted by Vault, scoped to that job's own key prefix. This page covers the job, its sizing and its network path. The Vault engine behind it is in the secrets-engines concept. ufw does not filter its port, because Podman publishes it through DNAT."
tags: [redis, cache, vault, firewall, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: redis-jobspec
    resource: deployments/infrastructure/services/redis.hcl
  - id: infra-database
    resource: deployments/infrastructure/database.tf
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: embark-jobspec
    resource: deployments/applications/services/embark.hcl
  - id: hashistack-server-playbook
    resource: bootstrap/playbooks/configure_hashistack_server.yml
---

# Redis cache

A shared cache on radxa-dragon-q6a. It stores nothing worth keeping. Its one
caller today is embark. How Vault mints each caller's user, the apply order
inside the infrastructure root, the `redis` mount name, and the lease traps
are in [Vault's dynamic secrets engines](/components/vault-secrets-engines.md).
How embark uses the cache is in [embark](/components/embark.md).

## The pieces

| Piece | Where |
| --- | --- |
| Job `redis`, `redis:7-alpine`, port 6379, pinned to radxa-dragon-q6a | `deployments/infrastructure/services/redis.hcl` |
| `nomad_job.redis` with `detach = false` | `deployments/infrastructure/services.tf` |
| Firewall: 6379 from jetson-orin-nano (.46) and firebat (.30), which ufw does not enforce (below) | `local.firewall_rules["redis"]`, same file |
| Admin password (the `default` user) | `random_password.redis_admin`, KV `default/redis/admin`, `deployments/infrastructure/secrets.tf` |
| Consumers, engine connection and roles | `local.redis_cache_consumers` and the rest of `deployments/infrastructure/database.tf` |

Only the `default` user's password is templated into the job, into
`secrets/redis.conf`. Vault's `redis-database-plugin` logs in with it to
create and drop every caller's user. No caller reads it.

## Two nodes must reach 6379

The caller's node, and Vault's. Vault runs on firebat (`192.168.2.30`, per
`vault_server_ip_address` in
`bootstrap/playbooks/configure_hashistack_server.yml`), and
`vault_database_secret_backend_connection.redis` dials `192.168.2.50:6379` at
apply time and on every mint and revoke.

The `redis` firewall entry admits `.46` and `.30`. The rule started as
`192.168.0.0/16` (fab7e53) and was narrowed to `.46` in da5e3d5. The
LAN-wide rule stayed on radxa until 2026-11-24, when `.30` was added and the
LAN-wide rule was deleted by hand.

None of these rules filter anything. The job publishes 6379 through Podman's
bridge, and netavark DNATs it to the container before ufw sees it, so the
packet takes FORWARD, which ufw accepts. On 2026-11-24, with the LAN-wide
rule gone, ubuntu (`.47`) still opened a TCP connection to
`192.168.2.50:6379`. The per-caller ACL users below are what keep the LAN
out. See [Host firewall](/components/host-firewall.md).

## Each caller gets its own key prefix

The minted user's rule is `+@read +@write +@connection ~<job>:*`, so a caller
can only touch keys starting `<job>:`. embark's `config.toml` sets no prefix,
so this relies on embark's own key naming, which this repo does not check.
Scripting (`EVAL`) and pub/sub are left out on purpose.

## It is a cache, by configuration

- `save ""` and `appendonly no`: a restart is a cold cache, not lost data.
  The same choice means minted users, which are in memory only, vanish on
  every restart. The recovery is in the secrets-engines concept.
- `maxmemory 384mb` with `allkeys-lru` under a 512 MB task limit. Without
  `maxmemory` Redis grows until Nomad OOM-kills it. The gap covers overhead
  and fragmentation that `maxmemory` does not count.

## Sizing, as recorded in 528ef7f

- `maxmemory` went from 96mb to 384mb and the task from 128 to 512 MB when
  OpenViking's reranker started sending embark new traffic.
- `cpu = 500`, up from 200, is a share, not a ceiling (nothing sets
  `cpu_hard_limit`). At 200 Redis got under 3% of a contended radxa, which fits
  embark's read timeouts. Redis runs commands on one thread, so the share
  cannot cost more than one core. The contention reading is unverified against
  node metrics.
- radxa's reservations add up to about 6.7 GB steady, plus about 1.3 GB while
  the backups run. That sum comes from the jobspecs, not `free -m`.

## Adding a consumer

1. Add the job id to `local.redis_cache_consumers` in
   `deployments/infrastructure/database.tf`.
2. Add the job's node to `local.firewall_rules["redis"]`, and add `.30` for
   Vault if it is not there yet.
3. In the jobspec, set `vault { role = "redis-cache-<job>" }`, keep the job id
   unchanged, and prefix every key with `<job>:`.

No Redis exporter and no alert exist, so a dead cache shows up only in the
consumer's own logs.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- commit `528ef7f`
- commit `da5e3d5`
