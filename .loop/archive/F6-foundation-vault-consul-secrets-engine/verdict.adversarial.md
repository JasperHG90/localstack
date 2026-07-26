---
verdict: pass
tree: 5d0f808eddbf8c3515c6a35070e1f8d07a761c9a
---

# Adversarial review — F6-foundation-vault-consul-secrets-engine

## Verdict: PASS

The implementation satisfies every F6 acceptance criterion. The repo gate
(`just pre_commit`) runs green here (check-json/yaml/ast, detect-private-key,
nomad-fmt, terraform-fmt, terraform-validate all Passed). Config-split is
honored, least-privilege holds against the eval-7 guardrail, TTLs sit in band,
and the running static-token path is untouched. One latent defect (session ACL
scoping) is recorded below; it does not break any F6 eval or gate, grants no
unintended privilege, and is deferrable to F8 — so it does not block this
commit, but F8 must not inherit its false assumption.

## Premise & operator-fork check

- The operator's binding resolution (Ansible owns the scoped `deploy` Consul
  ACL policy via `community.general.consul_policy`; Terraform references it by
  name via `consul_policies`) is implemented exactly as directed:
  `bootstrap/playbooks/enable_consul_secrets.yml:39-58` creates the policy;
  `deployments/infrastructure/consul_deploy_role.tf:22` attaches it by name.
  This preserves the operative invariant (no Consul management token in
  Terraform). Judged against the resolution, not the ticket's literal wording.

## Config-split integrity — CLEAN

- Terraform declares NO `vault_consul_secret_backend` mount (grep of
  `deployments/**` returns only `_role`). Ansible owns the mount enable
  (`enable_consul_secrets.yml:69-76`) and `consul/config/access`
  (`:80-90`). No dual-ownership collision.
- Terraform holds no Consul token: the only `consul...token`/`management`
  hits in `deployments/infrastructure/*.tf` are code comments
  (`consul_deploy_role.tf:8,10`). The role authenticates to Vault only.

## Least-privilege — CLEAN against eval 7

- Policy (`enable_consul_secrets.yml:42-57`) grants only:
  `key_prefix "terraform/" = write`, `session_prefix "terraform/" = write`,
  `service "minio" = read`, `service "postgres-db" = read`,
  `node_prefix "" = read`. No `acl`, no `operator`, no global
  `key_prefix "" = write`, no `service_prefix "" = write`.
- Eval 7 (out-of-scope KV write + `consul acl token list` denied) holds by
  inspection: nothing in the policy grants write outside `terraform/` or any
  `acl` capability. Compare the god-mode agent policy
  (`bootstrap/roles/consul_server/files/agent_policy.hcl`, all
  `*_prefix "" = write`) — the deploy policy is strictly narrower.
- `node_prefix "" = read` is read-only and justified/commented
  (`enable_consul_secrets.yml:37-38`, Q3-sanctioned for `consul_service`
  node-address resolution). Not an over-grant.

## Idempotency — mirrors F5

- Engine-enable guard is the exact F5 pattern: `vault secrets list -format=json`
  (changed_when false) then enable `when: "'consul/' not in (... | from_json)"`
  (`enable_consul_secrets.yml:60-76`; cf. `nomad_server/tasks/main.yml:275-289`).
- `community.general.consul_policy` is create-or-update idempotent (same module
  the repo already uses for `agent_policy`,
  `consul_server/tasks/main.yml:101-106`).
- `consul/config/access` re-writes each run (changed_when true) — same
  non-idempotent-but-safe overwrite as F5's `nomad/config/access`
  (`nomad_server/tasks/main.yml:293-303`). Acceptable; mirrors precedent.
- `no_log: true` on the config/access task (`:90`) protects the embedded mgmt
  token; the policy task relies on the module's own `no_log` token param, as
  the agent_policy precedent does.

## TTL / correctness — CLEAN

- Role `ttl=1800`, `max_ttl=3600` (`consul_deploy_role.tf:23-24`) land inside
  the eval's ~1800-3600s band (evals 3 & 4). Correctly placed on the role,
  not on a `consul/config/lease` — the Consul secrets engine carries per-role
  TTL directly (unlike F5's Nomad engine, which needed `nomad/config/lease`).
  The implementer correctly did NOT copy F5's config/lease task.
- `consul/config/access address="127.0.0.1:8500"` (`:84`) with default http
  scheme is correct (Vault Consul engine `address` is `host:port`; Consul is
  local to the manager and http, matching the provider/agent config). Eval 2
  (`vault read consul/config/access` shows address+scheme) passes.

## Static-token path — UNTOUCHED

- `git diff --stat` shows only `bootstrap/justfile` (+1, wires the playbook
  after `seed_vault.yml`, correct ordering) and `.loop/ledger.json` (harness).
  `providers.tf`, both deploy justfiles, and `.env` are not touched. Non-goal
  respected: the deployer keeps its static token until F8.

## Findings

### F1 (MEDIUM, latent — does not block F6; must be resolved in F8)
`session_prefix "terraform/" { policy = "write" }`
(`enable_consul_secrets.yml:46-48`) does not do what the ticket's Q6 intended
(enable Terraform state locking). Consul `session`/`session_prefix` rules are
matched against the NODE NAME a session is bound to, not against a KV key
prefix — consistent with the repo's own agent policy pairing `session_prefix ""`
with `node_prefix ""`/`agent_prefix ""` (agent_policy.hcl:1-12). Terraform's
Consul state backend creates its lock session on the local agent node (an Orange
Pi hostname), which will never match the prefix `terraform/`. Consequences:
- The grant is inert: it confers no real session:write, so it is NOT an
  over-grant and does not weaken eval 7.
- It will NOT enable state locking when F8 cuts the deployer over to the
  brokered token; a locked `terraform apply`/`init` would be denied
  session:write and fail to acquire the state lock.

Why this does not fail F6: the DoD is the eval marker, and marker eval 5
(`consul kv put/get terraform/_f6probe`) is a raw KV op that takes no lock — it
passes on `key_prefix "terraform/" = write` alone. No F6 eval exercises a lock
session, and F6 explicitly does not run the deployer against the brokered token.
The rule was ticket-sanctioned (Q6), so it is not a scope violation.

Required for F8 (flagging so the assumption is not inherited silently): either
grant `session_prefix "" { policy = "write" }` (broader; the only way to cover
the lock session on the actual node), scope it to the real node name(s), or
run the backend with locking disabled — and add a genuine put/get/LOCK-cycle
eval, since the current marker eval 5 cannot catch this.

## Positive eval trace (by inspection; live cluster unreachable, as briefed)

1. Engine mounted — Ansible enable, `type consul` → PASS.
2. `config/access` configured — address+scheme written → PASS.
3. `consul/roles/deploy` — policy by name + ttl/max_ttl 1800/3600 in band → PASS.
4. `consul/creds/deploy` — lease_duration = role ttl 1800, bounded → PASS.
5. State-KV put/get under `terraform/` — `key_prefix "terraform/" = write` → PASS.
6. Service reads `minio`/`postgres-db` — named service reads + node_prefix read
   → PASS.
7. Out-of-scope write + `acl token list` denied — no matching grant → PASS.

Relevant files:
- /home/vscode/workspace/bootstrap/playbooks/enable_consul_secrets.yml
- /home/vscode/workspace/deployments/infrastructure/consul_deploy_role.tf
- /home/vscode/workspace/bootstrap/justfile
