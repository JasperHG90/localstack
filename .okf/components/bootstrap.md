---
type: component
title: Ansible bootstrap
description: "bootstrap/ installs and wires Consul, Vault and Nomad on the five nodes, then hands Vault the management tokens it brokers from. Every playbook is meant to be re-runnable, but seed_vault.yml rewrites the bootstrap secrets from the environment on every run, and the HashiStack versions move only through one group_vars file."
tags: [ansible, bootstrap, consul, vault, nomad, upgrade, tailscale]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: bootstrap-justfile
    resource: git:3ec5d1e:bootstrap/justfile
  - id: group-vars
    resource: git:3ec5d1e:bootstrap/inventory/group_vars/all.yml
  - id: install-dependencies
    resource: git:3ec5d1e:bootstrap/playbooks/install_dependencies.yml
  - id: seed-vault
    resource: git:3ec5d1e:bootstrap/playbooks/seed_vault.yml
  - id: vault-server-role
    resource: git:3ec5d1e:bootstrap/roles/vault_server/tasks/main.yml
  - id: nomad-server-role
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/tasks/main.yml
  - id: nomad-server-template
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/templates/nomad.hcl.j2
  - id: enable-consul-secrets
    resource: git:3ec5d1e:bootstrap/playbooks/enable_consul_secrets.yml
  - id: unseal-script
    resource: git:3ec5d1e:scripts/unseal_vault.sh
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
  - id: U2-upgrade-vault-2x
    resource: loop:U2-upgrade-vault-2x
  - id: U3-upgrade-nomad-2x
    resource: loop:U3-upgrade-nomad-2x
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
  - id: F9-foundation-scope-nomad-workloads-policy
    resource: loop:F9-foundation-scope-nomad-workloads-policy
---

# Ansible bootstrap

`bootstrap/` turns five Ubuntu hosts into a Consul, Vault and Nomad cluster and
leaves Vault holding the Consul and Nomad management tokens. Everything above
that line is Terraform ([the two Terraform
roots](/components/terraform-roots.md)). The split is deliberate, and
`enable_consul_secrets.yml` calls it the config-split invariant: anything that
needs the Consul or Nomad management token stays in Ansible. Terraform only ever
sees short-lived tokens that Vault brokers from them.

The operator steps for SSH keys and passwordless sudo are in
`bootstrap/README.md`. Where the bootstrap secrets live is
`docs/reference/bootstrap-secrets.md`.

## Layout

- `bootstrap/inventory/cluster.ini`: one `manager` (firebat) and four `worker`
  hosts. Per-node detail is [the cluster nodes](/components/cluster-nodes.md).
- `bootstrap/inventory/group_vars/all.yml`: `hashistack_versions`, the only
  place the Consul, Vault, Nomad and nomad-driver-podman versions are declared.
- `bootstrap/ansible.cfg`: inventory, roles path, `become` via sudo, and the
  repo's `.ssh/id_rsa` as the key.
- `bootstrap/requirements.yml`: three pinned collections (`containers.podman`,
  `community.general`, `ansible.posix`), installed by `just setup`.
- `bootstrap/playbooks/`: nine playbooks. `just bootstrap` runs them in this
  order.

| # | Playbook | Hosts | What it does |
|---|---|---|---|
| 1 | `install_dependencies.yml` | all | apt pin, dist-upgrade, Podman, ufw, CNI plugins, HashiStack packages, bridge sysctls |
| 2 | `configure_hashistack_server.yml` | manager | roles `consul_server`, `vault_server`, `nomad_server`, in that order |
| 3 | `configure_hashistack_clients.yml` | worker | roles `consul_client`, `nomad_client` |
| 4 | `seed_vault.yml` | manager | `bootstrap/` KV2 mount, then `bootstrap/tailscale` and `bootstrap/github` from env |
| 5 | `enable_consul_secrets.yml` | manager | Consul `deploy` ACL policy and Vault's `consul/` engine |
| 6 | `configure_podman.yml` | all | ghcr.io `auth.json` for the user and for root |
| 7 | `configure_nvidia_ctk.yml` | `jetson_nano` | nvidia runtime as root Podman's default |
| 8 | `configure_tailscale.yml` | all | manager is a subnet router for 192.168.2.0/24, workers stop tailscaled |
| 9 | `configure_network.yml` | all | role `firewall`: ufw default deny and the HashiStack ports |

## The server roles depend on each other

The three server roles run on one host and each reads files the one before it
wrote:

1. `consul_server` runs `consul acl bootstrap` once and keeps the management
   token at `/opt/consul/bootstrap_token`. It then creates the agent policy
   and token.
2. `vault_server` reads that token to create Vault's Consul policy and token,
   because Vault's storage is Consul (`storage "consul"`, path `vault/`). It
   runs `vault operator init` once, writes the output to
   `/opt/vault/init.json`, and unseals with the first three keys whenever it
   finds Vault sealed.
3. `nomad_server` waits for both, bootstraps Nomad ACLs into
   `/opt/nomad/init.json`, then uses Vault's root token from `init.json` to
   set up the `jwt-nomad` auth mount, the `nomad-workloads` role and policy,
   and the `nomad/` secrets engine with `config/access` and a 30m/1h lease.

`enable_consul_secrets.yml` does for Consul what step 3 does for Nomad. It
was added by F6 as its own playbook. It writes the Consul `deploy` policy that
bounds what both Terraform roots can touch in Consul, so a new
`consul_service` lookup in Terraform needs a line here first.

The workload policy template
(`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`) keeps a
comment about the three grants F9 removed. The comment is inside the policy
text, so Vault stores it and `vault policy read` prints it. It names the ticket
but not the removed paths, so a grep for a revoked path finds nothing.

## Day 0 and day 2

`configure_podman.yml` and `configure_tailscale.yml` each check for
`/opt/vault/init.json`. With it they read their secret from Vault's
`bootstrap/` mount using the root token. Without it, on day 0, they read
`GITHUB_USER`, `GITHUB_PAT` and `TAILSCALE_AUTH_KEY` from the environment.
Those three come from `.devcontainer/.env` through the container's
environment, not from `bootstrap/.env`, whose example file does not list
them.

The trap is step 4. `just bootstrap` runs `seed_vault.yml` every time, and it
writes both secrets from the environment unconditionally. A full day-2 run
therefore resets `bootstrap/tailscale` and `bootstrap/github` to whatever the
shell holds, which undoes a rotation made in Vault and writes empty values when
the variables are unset. Run single playbooks on day 2. The unbuilt fix is [the
credential rotation proposal](/proposals/bootstrap-credential-rotation.md).

No playbook has a dry-run gate, and no pre-commit hook runs the
`.ansible-lint` file that exists. The only checks that read `bootstrap/` are
CLI tests: `cli/tests/commands/test_breakglass_runbook_facts.py` pins runbook
facts to the inventory, the `vault_server` role and `configure_network.yml`,
and `localstack deps` reads `group_vars/all.yml`.

## Pinned versions

`install_dependencies.yml` writes `/etc/apt/preferences.d/hashistack` from
`hashistack_versions` BEFORE its `upgrade: dist` task, at priority 990. U1
found the order mattered: a pin that lands after the dist-upgrade pins
nothing. 990 is below 1000 on purpose, so apt never downgrades a node that is
ahead of the pin. Instead a later task reports that node as `DRIFT` and leaves
the choice to the operator.

The CLI's `localstack deps` reads the same file to install matching client
binaries ([the localstack CLI](/components/localstack-cli.md)), so moving a
version is one edit for both.

U1 to U4 moved the cluster from Consul 1.22.6, Vault 1.21.4 and Nomad 1.11.3 to
the current 2.0 line. All four were applied by hand on the nodes, with the pins
recorded in commit `547cab0`, and closed afterwards, so their plans are the only
upgrade runbooks and no `docs/` page replaces them. What they measured:

- Vault 2.0 still accepts the wildcard in the identity-templated
  `nomad-workloads` policy (checked on a `vault server -dev` first).
- The Nomad advertise fix in `c744b92` had to land before any restart. The
  comment in `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` records the
  outage: with only `bind_addr = "0.0.0.0"`, a restart can advertise the podman
  bridge `10.88.0.1`, and four of five nodes dropped. Both Nomad templates now
  advertise one address explicitly.
- Vault stayed unsealed through a Consul server restart.
- A Consul snapshot restores only into the version that took it, so take one
  after each upgrade too. Neither the Vault nor the Consul restore was
  rehearsed, which both reflections name as the main gap.

## Unsealing

Two paths unseal Vault:

- Re-running `configure_hashistack_server.yml`, whose `vault_server` role
  reads the keys from `init.json` on the manager itself.
- `just unseal_vault`, which runs `scripts/unseal_vault.sh`. The script needs
  `VAULT_UNSEAL_KEY_1` to `_3`, `VAULT_ADDR` and `VAULT_TOKEN` in the
  environment. The token is not used by `vault operator unseal`, only by the
  guard. The CLI's breakglass runbook explains why the CLI prints this
  command and never runs it (`docs/reference/cli-breakglass.md`).

The unseal keys and the root token are stored together in
`/opt/vault/init.json` on the manager, owned by `vault` with mode 0600.
