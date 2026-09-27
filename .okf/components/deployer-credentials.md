---
type: component
title: Terraform deployer credentials
description: "How each Terraform root authenticates today: both run on the operator's localstack login session, whose Vault token carries the developer policy and whose Nomad and Consul tokens are brokered, plus the aliased nomad.manage provider that re-mints a management token every run. Also why the planned per-root deployer identities (F7, F12, F13) were dropped and what F8 still owns."
tags: [terraform, vault, nomad, consul, deployer, credentials]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: machine-roles-tf
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: infrastructure-providers-tf
    resource: git:3ec5d1e:deployments/infrastructure/providers.tf
  - id: applications-providers-tf
    resource: git:3ec5d1e:deployments/applications/providers.tf
  - id: infrastructure-justfile
    resource: git:3ec5d1e:deployments/infrastructure/justfile
  - id: applications-justfile
    resource: git:3ec5d1e:deployments/applications/justfile
  - id: env-py
    resource: git:3ec5d1e:cli/src/localstack_cli/commands/env.py
  - id: identity-tf
    resource: git:3ec5d1e:deployments/infrastructure/identity.tf
  - id: F7-foundation-deployer-vault-oidc-login
    resource: loop:F7-foundation-deployer-vault-oidc-login
  - id: F11-foundation-human-read-role
    resource: loop:F11-foundation-human-read-role
  - id: F12-foundation-deployer-privilege-split
    resource: loop:F12-foundation-deployer-privilege-split
  - id: F13-foundation-infrastructure-deployer
    resource: loop:F13-foundation-infrastructure-deployer
  - id: G2-nomad-ui-oidc-login
    resource: loop:G2-nomad-ui-oidc-login
  - id: F8-plan
    resource: git:3ec5d1e:.loop/plans/F8-foundation-deployer-provider-cutover.md
---

# Terraform deployer credentials

Neither Terraform root has an identity of its own. Both run as the person who
typed `just plan` or `just apply`, using the tokens from their
`localstack login` session. What that command does for a user is
`docs/reference/cli-login.md`. This page covers what each root does with
those tokens and why the design stopped here.

## What a run authenticates with

Every Terraform recipe in `deployments/infrastructure/justfile` starts with
`eval "$(uv run localstack env)"`, and so does every Terraform recipe in
`deployments/applications/justfile`. `cli/src/localstack_cli/commands/env.py`
exports four variables from the session and refuses if the session holds no
brokered tokens:

| Variable | Value | Consumed by |
|---|---|---|
| `VAULT_TOKEN` | the person's userpass token, carrying `developer` through the group | both bare `provider "vault" {}` blocks |
| `NOMAD_TOKEN` | a `nomad/creds/deploy` client token | both bare `provider "nomad" {}` blocks |
| `CONSUL_HTTP_TOKEN`, `CONSUL_TOKEN` | a `consul/creds/deploy` token | the Consul state backend, and the applications root's `consul` provider |

The Consul backend is configured at `terraform init`, before any provider or
data source exists. That is why a Vault read inside the configuration can
never feed it, and why the token has to arrive through the environment.
F8's plan called this its load-bearing design fork. Exporting the brokered
token before `init` settles it, but only where the export reaches
`terraform`.

It does not in most of the applications root. Its `init`, `destroy` and
`state_rm` recipes have no shebang, so `just` runs each line in a new shell
and the `eval` line's exports are gone before `terraform` starts. Only
`apply`, a shebang recipe, runs on the session. The same justfile sets
`dotenv-filename` to `.devcontainer/.env`, so the other recipes run on
whatever that file and the calling shell hold. Every infrastructure recipe has
a shebang and is not affected.

The other credentials each root needs come from Vault inside the run:

- **Applications root.** `minio`, `postgresql` and `bifrost` take admin
  credentials from `ephemeral "vault_kv_secret_v2"` reads, so they never
  enter state. The `consul` provider hardcodes its address because it does
  not read one from the environment. `bifrost` reads its endpoint off
  `null_resource.bifrost_ready` to get an ordering edge, since provider blocks
  take no `depends_on`.
- **Infrastructure root.** Nomad ACL objects need a management token, which
  the deploy token is not. The aliased provider below supplies it.

The Vault provider mints a child token before reading anything, so every
token that runs Terraform needs `auth/token/create`. The `default` policy
does not grant it, and no `vault_*` resource block mentions it. F7's policy
missed it.

## The `nomad.manage` provider

`deployments/infrastructure/machine_roles.tf` declares
`vault_nomad_secret_role.manage` (`type = "management"`), reads
`data.vault_nomad_access_token.manage`, and feeds that token to
`provider "nomad" { alias = "manage" }`. Four resources use it:
`nomad_acl_policy.deploy`, `nomad_acl_policy.dash_read`,
`nomad_acl_auth_method.oidc` and `nomad_acl_binding_rule.developer`. The
default provider keeps the deploy token.

The alias stays in `machine_roles.tf` beside the data source, not in
`providers.tf`. `.claude/rules/terraform-file-layout.md` names this as its one
exception, so the reason it must be re-read every run stays next to the read.

It also closes a loop F8's plan review found: the deploy token cannot write
the Nomad ACL policy that defines the deploy token. Only a management token
writes ACL policies, and no capability inside a policy grants that.

### Why the data source has no `depends_on`

The block titled `NO depends_on HERE, DELIBERATELY` records a measurement
from G2. With a `depends_on` on `vault_policy.developer`:

1. Terraform deferred the token read to apply time.
2. Refresh still ran first and configured the aliased provider from state,
   holding the previous run's token, dead after its 30-minute lease.
3. Refresh of `nomad_acl_auth_method.oidc` returned 403.

Any edit to the policy text triggered it, including a comment, because the
policy is a heredoc. It only fired when 30 minutes had passed since the last
run, so it looked intermittent. Moving the `depends_on` to the role made the
read happen at plan time, before the policy write, so it never protected
anything. The grant has to exist before the run.

The invariant it states: a provider fed by a short-TTL brokered credential
must re-read that credential every run. Anything that defers the read breaks
refresh. The cost is one fresh management token per plan, which Terraform
never revokes, so `vault-manage-*` tokens pile up until they expire within
the hour.

## The ceiling this leaves

The operator's Vault token is not a boundary. `developer` can write
`sys/policies/acl/*`, `identity/*` and `nomad/role/*`, so it reaches
anything short of the `root` policy in a few commands. Its own comment says
Developer and Deployer are one role here, by the operator's choice. What it
buys over the root token is a per-person credential that removing a group
member revokes. It gives no attribution, because no audit device is enabled.
[Vault human identity](/components/vault-identity.md) has the grants.

## The per-root deployer that was not built

- **F7** tried one scoped `deployer` policy behind an OIDC login for both
  roots. It failed plan review twice: the policy missed `auth/token/create`
  and could not run either root, and the grants the infrastructure root
  needed made it root-equivalent by rewriting itself. It was retired on
  2026-08-01 and split in two.
- **F12**, the applications root, measured a three-grant policy
  (`auth/token/create`, write on data and read on metadata under eight
  enumerated `default/<prefix>` paths) that planned clean and was denied all four
  escalation probes. The enumeration mattered: `default/*` would have exposed
  the operator's own password at `default/vault/operator`.
- **F13**, the infrastructure root, planned to move every `vault_policy` into
  Ansible so the deployer held no policy write. Its plan review found a
  second route of the same length. Rewrite `nomad/role/deploy` to
  `type = "management"`, read it, schedule a rootful podman job on the
  manager, and read `/opt/vault/init.json`.

All three were dropped. F11's `developer` group and D2's `localstack login`
shipped instead. Removing the escalation routes means taking identity and
Nomad role writes out of this root too, and that ticket was never written.

## What F8 still owns

F8 is blocked. Its plan predates D2 and describes the justfiles feeding the
backend `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` from static environment tokens.
The recipes no longer write that prefix, although the applications root's
dotenv load (above) is still a path for static tokens. What is left is its
last step: removing the
static tokens from `.devcontainer/.env.example` and whatever the devcontainer
still injects. `docs/reference/cli-login.md` explains how an injected root
`VAULT_TOKEN` outranks the session until `localstack env` replaces it. Several
comments still describe the pre-D2 state: `oidc.tf` says the default Nomad
provider reads the bootstrap token, and `machine_roles.tf` says the root runs
as root and that consuming the brokered Consul token is future work.

The Vault root token still exists in `/opt/vault/init.json` on the manager.
Ansible uses it. `localstack breakglass` prints the recovery runbook and
never reads or prints the token.
