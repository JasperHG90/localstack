---
type: component
title: The two Terraform roots
description: "deployments/infrastructure and deployments/applications are separate Terraform roots with separate Consul-stored state and no remote-state link. Applications reads what infrastructure made by static name through Vault and the Consul catalog, so infrastructure is applied first and a few literals must be kept equal by hand."
tags: [terraform, consul, vault, state, pre-commit, deployer]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: infra-backend
    resource: git:3ec5d1e:deployments/infrastructure/backend.tf
  - id: apps-providers
    resource: git:3ec5d1e:deployments/applications/providers.tf
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: infra-machine-roles
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: enable-consul-secrets
    resource: git:3ec5d1e:bootstrap/playbooks/enable_consul_secrets.yml
  - id: tf-validate
    resource: git:3ec5d1e:scripts/tf_validate.sh
  - id: pre-commit
    resource: git:3ec5d1e:.pre-commit-config.yaml
  - id: root-justfile
    resource: git:3ec5d1e:justfile
  - id: cli-env
    resource: git:3ec5d1e:cli/src/localstack_cli/commands/env.py
  - id: F6-foundation-vault-consul-secrets-engine
    resource: loop:F6-foundation-vault-consul-secrets-engine
  - id: F11-foundation-human-read-role
    resource: loop:F11-foundation-human-read-role
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
---

# The two Terraform roots

Two roots deploy everything above the HashiStack itself. They keep separate
state, and nothing in Terraform links them. Applications finds what
infrastructure made by reading it back out of Vault and the Consul catalog
under fixed names. So infrastructure is applied first, and a handful of
literals must match across roots with no check behind them.

How the `.tf` files inside a root are split is the local rule
`.claude/rules/terraform-file-layout.md`. It is not repeated here.

## What each root owns

`deployments/infrastructure` owns the platform the apps stand on:

- the `secret` KV2 mount (`vault_mount.kvv2`, `secrets.tf`) that every KV
  write in both roots lands in
- every Nomad dynamic host volume, including those mounted by application
  jobs (`services.tf`)
- the platform jobs: postgres, minio, haproxy, prometheus, grafana, alloy,
  node-exporter, the two oauth2-proxy instances, nats, redis, acme and the
  two backup jobs
- Vault identity, the OIDC provider and every OIDC client (`identity.tf`,
  `oidc.tf`), and the machine roles Vault brokers (`machine_roles.tf`)
- Vault's Redis database secrets engine and its `cache-*` roles (`database.tf`)
- the GCS backup bucket and its service account (`storage.tf`, the only use
  of the `google` provider, which needs the gcloud credentials the
  devcontainer bind-mounts)

`deployments/applications` owns the workloads that change weekly: hermes, loki,
tempo, registry, embark, openviking, ov-dash, driftwatch, dash, registry-ui and
bifrost; their MinIO buckets and IAM (`storage.tf` and
`deployments/applications/modules/bucket/`); their Postgres roles and databases
(`database.tf`); and the Bifrost virtual keys.

## State and credentials

Both roots declare an empty `backend "consul" {}`. The address and path come
from each root's `vars/backend-config.hcl` at `terraform init`:
`terraform/infrastructure` and `terraform/applications` on the Consul server at
`192.168.2.30:8500`. Consul also holds Vault's storage (`vault/`), so one Consul
outage takes out Vault and both states at once. U4 treated it that way: snapshot
before and after, and a clean `terraform plan` in both roots as the proof that
state survived. No scheduled Consul snapshot job exists.

The Terraform recipes in `deployments/*/justfile` run
`eval "$(localstack env)"` before `terraform`. That exports four values from the
CLI session:

- `VAULT_TOKEN`: the operator's userpass session, carrying the `developer`
  policy. F11 wrote that policy to cover both roots and retire the root token.
- `NOMAD_TOKEN`: brokered from `nomad/creds/deploy`.
- `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN`: brokered from `consul/creds/deploy`.

The eval only reaches `terraform` in a recipe with a bash shebang, because
`just` runs each line of a plain recipe in its own shell. Every infrastructure
recipe and applications' `apply` have one. Applications' `init`, `destroy` and
`state_rm` do not, so they run with whatever tokens the calling shell already
holds. Infrastructure calls `uv run localstack env`, applications calls bare
`localstack env`, and applications has no `plan` recipe.

The brokered tokens are narrow, and that shapes what a root can add:

- The Consul `deploy` policy is written by Ansible, not Terraform
  (`bootstrap/playbooks/enable_consul_secrets.yml`). It grants write on
  `terraform/` and sessions, which is all the state backend needs. It also
  grants read on exactly two services, `minio` and `postgres-db`, plus
  `node_prefix` read. A new `data "consul_service"` in applications will be
  denied until that playbook grows a line and is re-run.
- The Nomad `deploy` policy (`nomad_acl_policy.deploy`, `machine_roles.tf`)
  allows `submit-job`, `read-job`, the `host-volume-*` capabilities and
  `mount-readwrite` on every host volume, and nothing else. Any Nomad ACL
  resource must use `provider = nomad.manage`, the aliased provider fed by a
  freshly brokered management token.

The `NO depends_on HERE, DELIBERATELY` block in `machine_roles.tf` records the
one measured trap in that alias: deferring the token read to apply time makes
refresh configure the provider from the last run's token, which died at its
30 minute lease. It 403s only when more than 30 minutes have passed, so it
reads as intermittent. Each plan also mints a management token that lives
until its lease ends.

## How applications reads infrastructure

There is no `terraform_remote_state` anywhere. The channels are:

| What applications needs | How it gets it | Written by |
|---|---|---|
| MinIO and Postgres addresses | `data "consul_service"` for `minio` and `postgres-db` | the infra jobs registering in Consul |
| MinIO and Postgres admin credentials | `ephemeral "vault_kv_secret_v2"` at `default/minio/localstack` and `default/postgres/localstack` | `deployments/infrastructure/secrets.tf` |
| OIDC client ids for memex and the Hermes dashboard | `data "vault_identity_oidc_client_creds"` by client name | `deployments/infrastructure/oidc.tf` |
| A host volume to mount | the volume name in the jobspec | `deployments/infrastructure/services.tf` |
| Vault JWT roles for its jobs | the role name in the jobspec | `deployments/infrastructure/machine_roles.tf` |

The `minio`, `postgresql` and `bifrost` providers in
`deployments/applications/providers.tf` are configured from these reads. So a
plan of applications fails at provider setup, before any resource, when MinIO or
Postgres is not registered in Consul or when the externally seeded
`default/bifrost/credentials` is missing. The `bifrost` provider also reads
`null_resource.bifrost_ready`, which polls Bifrost's `/health` after each
redeploy. Provider blocks take no `depends_on`, and the comment in
`providers.tf` explains why a resource reference is used instead.

Some values are literals that must equal something in the other root, and the
only link is a comment beside each:

- `openviking_account` and `openviking_user` on `nomad_job.hermes` must equal
  the `hermes` entry of infrastructure's `var.vault_openviking_workloads`.
- `hermes_dashboard_public_url` must equal infrastructure's
  `hermes_dashboard_redirect_url` minus `/auth/callback`.
- The upstreams of the two oauth2-proxy jobs in
  `deployments/infrastructure/services.tf` are loopback addresses for dash and
  registry-ui in applications, colocated on the same node.
- Apart from MinIO and Postgres, which come from the Consul catalog, every
  node address is a literal (`*_host = "192.168.2.50"`). The node map is
  [node placement](/nodes/placement.md).

## Apply order

Apply infrastructure, then applications. A fresh cluster also needs secrets
seeded by hand. The Bifrost ones are `default/bifrost/credentials`,
`ollama-personal`, `ollama-xebia` and `gemini` (the commands are in a comment
inside `nomad_job.bifrost`). The Hermes ones are the paths its jobspec names:
`default/hermes/github`, `telegram`, `email` and `nomad`.

Infrastructure cannot plan without `default/bifrost/credentials` either,
because `deployments/infrastructure/secrets.tf` reads it with a data source.
On an empty Vault that is circular: the `secret` mount it reads from is
created by the same root. The mount has to exist and the secret has to be
seeded before a full plan succeeds, and no runbook in the repo writes that
order down.

Reverse flow exists in one place. Infrastructure copies
`default/bifrost/credentials` into `default/prometheus/bifrost-admin`
(`deployments/infrastructure/secrets.tf`), because Prometheus's workload policy
only reads its own prefix. Rotating the Bifrost admin password without an
infrastructure apply leaves Prometheus scraping with the old one.

Ending every Hermes dashboard session is the other two-root operation: replace
the OIDC client in infrastructure, then apply applications so the job picks up
the new client id (`deployments/infrastructure/oidc.tf`).

## Inputs that are not in git

- `vars/prod.tfvars` in each root is gitignored (`**/vars/prod.tfvars`).
  `prod.tfvars.example` beside it lists the keys. Both need `secret_mount`.
  Infrastructure also needs `gcp_project`, `gcs_backup_bucket` and
  `telegram_alert_chat_id`. Applications also needs the Hermes identity values.
- `.ssh/id_rsa` at the repo root. Both roots carry a `null_resource.firewall`
  that runs `sudo ufw allow` over SSH, and `file()` reads that key, so even
  `terraform validate` fails without it. `just worktree_setup <path>` symlinks
  the key and copies both tfvars into a loop worktree for this reason.
- `.terraform.lock.hcl` is gitignored (`deployments/.gitignore`). Provider
  versions are fixed only by the `~>` constraints in `providers.tf`, so two
  machines can resolve different patch releases. Neither root declares the
  `random` provider it uses, so it resolves to the latest `hashicorp/random`.

The firewall rules only ever add. Deleting an entry leaves the rule on the node.
The two roots also differ in when they re-run: infrastructure's
`null_resource.firewall` carries a `timestamp()` trigger, so every apply re-adds
its rules and heals a rule another ufw write dropped. Applications' triggers
only on a change to the rule list or host, so its rules do not heal. [ufw rules
outside user.rules](/practices/ufw-rules-outside-user-rules.md) has the measured
behavior.

## Gates

`.pre-commit-config.yaml` runs two Terraform hooks on any `.tf` change:

- `terraform-fmt`: `terraform fmt -check -recursive` over the whole tree.
- `terraform-validate`: `scripts/tf_validate.sh`, which validates
  `deployments/infrastructure`, `deployments/applications` and
  `deployments/applications/modules/bucket` offline. It runs
  `init -backend=false` only when a root has no `.terraform/` yet, so it never
  touches Consul. A root that is already initialized validates against
  whatever provider schemas it holds.

Neither hook plans. A change that validates can still fail at plan on a
missing grant, a missing catalog entry or a missing seeded secret.

Moving blocks between files in a root is checked with
`scripts/tf_block_diff.py` and a final `terraform plan` reporting no changes,
as the file-layout rule describes. Commit `8a54775` was the move that split
infrastructure's 17 files, 10 of them named after a feature, into the current
subsystem files.

## Deployer tickets

F7, F12 and F13, which would each have given a root a narrower Vault identity,
were dropped. F8, moving the Nomad and Consul providers fully onto brokered
tokens, is blocked on a design fork. The credential side of both roots is
[the deployer credentials](/components/deployer-credentials.md). The ufw
behavior is also in [the host firewall](/components/host-firewall.md), and the
volumes in [host volumes](/components/host-volumes.md).
