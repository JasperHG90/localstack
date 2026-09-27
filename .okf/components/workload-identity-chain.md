---
type: component
title: The workload identity chain, as built
description: "Where each link of the Nomad-to-Vault workload identity chain is defined: Ansible owns the jwt-nomad mount, its config, the default nomad-workloads role and policy, and machine_roles.tf adds one dedicated role per job that needs more. Covers the apply order, the one-token rule every dedicated role must follow, and the traps in rendering and changing the shared policy."
tags: [vault, nomad, workload-identity, jwt, ansible, terraform]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: machine-roles-tf
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: nomad-server-tasks
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/tasks/main.yml
  - id: nomad-workloads-policy
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2
  - id: nomad-workloads-role
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json
  - id: nomad-server-config
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/templates/nomad.hcl.j2
  - id: oidc-tf
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: workload-identity-explanation
    resource: git:3ec5d1e:docs/workload-identity.md
  - id: F1-foundation-nomad-wi-jwt-trust
    resource: loop:F1-foundation-nomad-wi-jwt-trust
  - id: F9-foundation-scope-nomad-workloads-policy
    resource: loop:F9-foundation-scope-nomad-workloads-policy
  - id: F10-foundation-nomad-oidc-issuer
    resource: loop:F10-foundation-nomad-oidc-issuer
  - id: R5-rollout-memex-oidc-auth
    resource: loop:R5-rollout-memex-oidc-auth
---

# The workload identity chain, as built

How the chain works, and the conventions a jobspec follows (named `identity`
blocks, one audience per verifier, `change_mode = "noop"` for file
identities), is `docs/explanation/workload-identity.md`. This page is the map
for someone changing it: which file owns each link, what order they apply
in, and what to watch when editing. Nomad's discovery document is
[Nomad's OIDC discovery](/components/nomad-oidc-discovery.md).

## Who owns each link

| Link | Owner | Where |
|---|---|---|
| Default identity (`aud = ["vault.io"]`, `ttl = "1h"`) | Ansible | `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`, `vault { default_identity }` |
| Nomad's `oidc_issuer` | Ansible | same template, set from `nomad_oidc_issuer` in `bootstrap/playbooks/configure_hashistack_server.yml` (F10) |
| `jwt-nomad` mount and its config | Ansible | `bootstrap/roles/nomad_server/tasks/main.yml` |
| Default role `nomad-workloads` | Ansible | `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json` |
| Shared policy `nomad-workloads` | Ansible | `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` |
| Dedicated roles and their policies | Terraform | `deployments/infrastructure/machine_roles.tf` |
| Identity-token roles a job mints from | Terraform | `deployments/infrastructure/oidc.tf` (`openviking_workload`) |
| Which role a job uses | the jobspec | `vault { role = "..." }` |

Ansible runs its tasks with the Vault root token read from
`/opt/vault/init.json` on the manager, and every `vault write` there reports
`changed` on every run. The apply order is fixed: `just bootstrap` (in
`bootstrap/justfile`) first, then the infrastructure root (roles and
policies), then the root that holds the job. A dedicated role
named in a jobspec before its Terraform exists leaves the task unable to log
in.

## How the mount is wired

`auth/jwt-nomad/config` sets `jwks_url` to Nomad's JWKS over loopback,
`jwt_supported_algs = RS256,EdDSA` and `default_role = nomad-workloads`. It
sets no `bound_issuer` and no discovery URL. Vault checks the signature
against Nomad's keys over loopback and never the `iss` claim, so setting
`oidc_issuer` in F10 changed nothing for Vault. It only gave MinIO and memex
a discovery document to point at.

The shared policy is templated on
`identity.entity.aliases.<accessor>.metadata.nomad_namespace` and
`.nomad_job_id`, and Ansible bakes the mount's accessor into the text when it
renders the template. Recreating the mount changes the accessor, so the
policy must be rendered again or it matches nothing.

Vault's JWT method creates an entity and an alias per job on first login and
owns them. Terraform cannot set metadata on them without fighting the mount.
That is why `oidc.tf` writes a workload's OpenViking account as a literal in
its own role, instead of reading entity metadata as the human role does.

## Dedicated roles in `machine_roles.tf`

Four families today, all the same shape: a `vault_policy` naming the extra
path, and a `vault_jwt_auth_backend_role` on `jwt-nomad` bound to one
`nomad_job_id`.

| Role | Extra grant | Job |
|---|---|---|
| `acme` | write `secret/data/default/haproxy/tls` | `deployments/infrastructure/services/acme.hcl` |
| `dash` | read `nomad/creds/dash_read` | `deployments/applications/services/dash.hcl` |
| `redis-cache-<job>` | read `redis/creds/cache-<job>` | `embark` today |
| `<job>` from `var.vault_openviking_workloads` | read `identity/oidc/token/openviking-<job>` | `hermes`, `leo-consumer` |

Every dedicated role has to copy three things from the Ansible role, and
nothing checks that it does:

1. **Both policies in `token_policies`**, the one-token rule.
2. **The same `claim_mappings`**, or the shared policy is attached and
   matches nothing.

   The explanation page gives the reason for both, with `acme` as the
   example.
3. **`token_period = 1800` and `token_explicit_max_ttl = 0`.** Without them
   the token is capped by the system max TTL instead of renewing for the life
   of the allocation.

Per-job roles instead of a wider shared policy is
[ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md).
The redis engine's first version shipped one shared role gated on
`nomad_namespace = "default"`, which is nearly every job, and was redone per
job for that reason.

A job reading an identity token mints a new one on every read. `hermes.hcl`
renders it with `change_mode = "noop"`, because `restart` restarted Hermes on
every consul-template poll. That is why the workload identity-token TTL is a
month: it has to outlast the allocation.

## Changing the shared policy

F9 removed the shared policy's `bootstrap/*` grants and its cluster-wide
listing. What it grants now, and what that still leaks, is in the
explanation page. Two traps from that ticket:

- **Render through Ansible, never by hand.** The template double-escapes its
  Vault placeholders for Jinja. F9's first runbook told the operator to
  render it by hand, which would have written a policy matching nothing and
  locked out all fifteen default-role jobs, haproxy included. Every gate was
  green on it.
- **Do not restate a removed grant in a comment.** Vault stores policy text
  verbatim, so a comment naming the old path makes a grep for that grant
  match. The template's trailing comment exists to say this.

## Verifiers other than Vault

memex (R5) verifies a raw workload JWT itself, against Nomad's JWKS, with
`aud = memex` and a grant rule on `nomad_job_id`
(`deployments/applications/services/memex/auth_oidc.json`). MinIO trusts the
discovery document with `aud = minio`. Neither touches `jwt-nomad`. The
audience registry is in the explanation page.

## History

F1 wrote the chain down and proved a keyless read with a probe job. It noted
that `nomad alloc fs` refuses to read `secrets/`, so proving a rendered
secret means printing it to the task's logs. F9 narrowed the shared policy.
F10 turned on discovery. `acme` was the first dedicated role and is the
pattern the others copy.
