---
type: component
title: Hermes, the agent gateway
description: "How the hermes job is assembled across both Terraform roots: three tasks on radxa, a loopback sidecar that keeps a rotating OpenViking token out of Hermes's environment, Bifrost for every model call, and a Vault OIDC client for Hermes Desktop. Lists the cross-root literals and the traps that shaped it."
tags: [hermes, agent, openviking, bifrost, vault, oidc, nomad]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: hermes-jobspec
    resource: worktree:deployments/applications/services/hermes.hcl
  - id: ov-auth-proxy
    resource: git:3ec5d1e:deployments/applications/services/hermes/ov_auth_proxy.py
  - id: hermes-dockerfile
    resource: git:3ec5d1e:deployments/applications/services/hermes/Dockerfile
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: infra-oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: infra-machine-roles
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: infra-variables
    resource: git:3ec5d1e:deployments/infrastructure/variables.tf
  - id: haproxy
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: dashboard-oidc-commit
    resource: git:fd5134d
  - id: hermes-0-21-commit
    resource: git:fe10862
  - id: U5-upgrade-hermes-bifrost-versions
    resource: loop:U5-upgrade-hermes-bifrost-versions
  - id: hermes-veerle-profile
    resource: git:3ec5d1e:.loop/plans/hermes-veerle-profile.md
---

# Hermes, the agent gateway

Hermes is one Nomad job, `hermes`, pinned to radxa-dragon-q6a (192.168.2.50).
It runs the Hermes agent behind Telegram, email and an OpenAI-compatible API
on 8642, plus the dashboard Hermes Desktop signs into on 9119. Its memory is
OpenViking and every model call goes through Bifrost on the same node. This
page describes the working tree as of 2026-09-27, which carries an
uncommitted edit to `hermes.hcl` (the `resources` block, below).

## The pieces

**The jobspec**, `deployments/applications/services/hermes.hcl`, has one
group with three tasks. All three share host networking, so `127.0.0.1` means
radxa itself.

| Task | Lifecycle | What it does |
|---|---|---|
| `config` | prestart, runs once | Copies `.env`, `config.yaml` and `SOUL.md` onto the `hermes_data` volume, rebuilds `/opt/data/skills-library` from a base64 bundle, fetches `JasperHG90/skills` as a tarball, and syncs the Bifrost model-provider plugin |
| `ov-auth-proxy` | prestart sidecar | Listens on 127.0.0.1:1934 and forwards to OpenViking on 1933 with a fresh bearer token from `secrets/ov_token` |
| `hermes` | main | Runs `start-hermes.sh`, which prunes clashing bundled skills and then `exec hermes gateway run`. s6 supervises the dashboard beside the gateway because `HERMES_DASHBOARD=1` |

**The image** is `ghcr.io/jasperhg90/hermes:<hermes_version>`, built from
`deployments/applications/services/hermes/Dockerfile`: the
`nousresearch/hermes-agent:v2026.8.31` base plus `jq` and `chromium`. The tag
(`0.21.0-1`) is set once, in `nomad_job.hermes` in
`deployments/applications/services.tf`, and `just rebuild_hermes` in
`deployments/applications/justfile` reads it from there. Build and push
before applying a tag change. `force_pull = true` re-pulls on every alloc.

**The applications root** holds the job, its inputs and its secrets:

- `nomad_job.hermes` in `services.tf` feeds `SOUL.md`,
  `ov_auth_proxy.py` and every `skills/**/SKILL.md` into the template.
- `vault_kv_secret_v2.hermes_api_server` and
  `vault_kv_secret_v2.bifrost_hermes_key` in `secrets.tf`, the second holding
  the value of `bifrost_virtual_key.hermes` (`services.tf`).
- Four KV paths seeded by hand, not by Terraform:
  `secret/default/hermes/{telegram,email,github,nomad}`.
- `local.firewall_rules.hermes` in `services.tf`: 8642 and 9119 from HAProxy
  (.30).

**The infrastructure root** holds its identity and its edge:

- `nomad_dynamic_host_volume.hermes_data` in `services.tf`, constrained to
  radxa.
- The `hermes` entry of `var.vault_openviking_workloads` (`variables.tf`),
  which drives three resources: `vault_identity_oidc_role.openviking_workload`
  (`oidc.tf`, published as `identity/oidc/token/openviking-hermes`), and
  `vault_policy.openviking_workload` plus `vault_jwt_auth_backend_role.openviking_workload`
  (`machine_roles.tf`). The JWT role is named `hermes`, which is what
  `vault { role = "hermes" }` in all three tasks selects.
- `vault_identity_oidc_key.hermes_dashboard`,
  `vault_identity_oidc_client.hermes_dashboard` and its key registration in
  `oidc.tf`, plus the client's entry in `local.oidc_provider_client_ids`.
- `backend hermesgw` in `services/haproxy.hcl`, routing
  `hermes-gateway.lab.orangecluster.nl` to 192.168.2.50:9119.

## Apply order and the links between roots

Apply the infrastructure root first. `data.vault_identity_oidc_client_creds.hermes_dashboard`
in the applications root fails until the client exists, and the tasks cannot
log in until the `hermes` JWT role does. Inside the applications root,
`null_resource.bifrost_ready` gates `bifrost_virtual_key.hermes`, which gates
the KV copy, which `nomad_job.hermes` names in `depends_on`.

Nothing but matching literals links the two roots. Three must agree:

- `openviking_account = "lab"` in `nomad_job.hermes` and `account` in
  `var.vault_openviking_workloads.hermes`. Change one and the job writes as
  one account while it believes it is another.
- `hermes_dashboard_public_url` in `services.tf` and
  `local.hermes_dashboard_redirect_url` in `oidc.tf`, minus `/auth/callback`.
  Vault refuses a callback it does not hold.
- The HAProxy node address in `dashboard.trusted_proxies` in the jobspec's
  `config.yaml`. The dashboard sets its cookies `Secure` from
  `X-Forwarded-Proto`, and only trusts that header from a listed proxy.

## Traps, and what measured them

**A rotating token cannot live in Hermes's environment.** Vault identity
tokens carry no lease, so consul-template re-reads one about every five
minutes and each read mints a different JWT. Rendered into env with a restart
on change, Hermes restarted on every poll. That was measured
(`88b089f`), and it is why `ov-auth-proxy` exists: Hermes holds the constant
endpoint `http://127.0.0.1:1934`, the sidecar reads the token file on every
request, and the template uses `change_mode = "noop"`. Hermes still demands an
API key, so `OPENVIKING_API_KEY` is a placeholder. The sidecar drops any
`Authorization` or `X-API-Key` Hermes sends and adds its own.

**Hermes writes to OpenViking account `lab`, not `jasper`.** OV2 created
per-person accounts and migrated nothing, so `lab` held 2920 objects and
`jasper` a few dozen. Pointing Hermes at `jasper` gave it an empty memory
(`oidc.tf`, comment on `openviking_workload`). The OpenViking side is
[The OpenViking database](/components/openviking-database.md) and
`docs/explanation/openviking-identity.md`.

**Hermes reads credentials from two channels.** The `config` task writes
`/opt/data/.env`. The `hermes` task gets a separate `secrets/file.env` with
`env = true`, plus an `env {}` block. The sets differ: `API_SERVER_KEY` and
`GH_TOKEN` exist only in the process environment. Add a credential to both or
check which one the consuming code reads.

**Config lines that look load-bearing and are not.** `plugins.enabled` does
not select the memory provider, because the plugin scanner skips
`plugins/memory`; `memory.provider: "openviking"` does. The provider ships in
the base image, so the Dockerfile installs nothing for it (`fe10862`).

**Bundled skills shadow ours.** The base entrypoint's `skills_sync.py` copies
bundled skills into `/opt/data/skills/`. Some share names with the IaC
library, and Hermes refuses ambiguous names, which silently broke cron jobs.
`start-hermes.sh` deletes the clashing copies after the entrypoint has run.

**The skills bundle is one template on purpose.** Each line is
`<base64 path>|<base64 body>`, generated by a `%{for}` loop inside a heredoc.
A top-level `for` directive emitting blocks is valid Terraform but not valid
HCL to `nomad fmt` (`4aeb2b4`).

**External skills are unpinned.** `external_skills_jasperhg90_ref = "main"`,
and a failed fetch is logged and ignored. The deploy succeeds with those
skills missing.

**The image must run as root.** s6-overlay's `/init` remaps UIDs and chowns
the volume, then drops to the `hermes` user, which needs `CAP_SETGID`. radxa's
podman driver is rootful, so this works. Do not set a non-root `user` on the
`hermes` task.

**No `memory_max` (uncommitted).** The working tree drops `memory_max = 2560`.
Oversubscription is off at the Nomad server, so the scheduler zeroed it and
2048 was always the cap. Applying it still replaces the alloc, because any
task-resources diff does. The measurement is in `services/embark.hcl`.

**The dashboard is admin-grade.** Hermes runs with `HERMES_YOLO_MODE=true`,
`approvals.mode: "off"`, a Nomad token and a GitHub PAT, so the dashboard
client is assigned to `operators` (developer and admin). Its ID token is the
bearer credential for seven days, with no refresh token and no revocation on
logout. Ending every session means replacing the client
(`terraform apply -replace=vault_identity_oidc_client.hermes_dashboard`), then
applying the applications root. `docs/explanation/vault-oidc-tokens.md` has
the general rules.

**Model names must exist in Bifrost's catalog.** The virtual key allows `*`,
but Bifrost still refuses a model its catalog lacks, with "Model not allowed
for this virtual key". The `bifrost_virtual_key` blocks must list
`provider_configs` alphabetically, or the post-apply consistency check fails
after the write lands (`services.tf`).

**Cron is registered by hand.** `services/hermes/register-cron.sh` posts
`/cron add` commands to the chat API. The jobs persist on the volume, so run
it once, and again only when a schedule changes.

## Leftovers

The firewall entry still admits 192.168.2.46 to 8642 from when memex called
the gateway. `ufw` rules here only add, so the line documents a rule that is
live on the node. Deleting it from Terraform removes nothing.

## History

Hermes reached memex with a Nomad workload identity JWT in R5 (`14e56ff`),
then moved its memory to OpenViking (`8d6d115`), first with a copied API key
and then with its own Vault identity token (`0007e46`, `88b089f`). U5 bumped
the base image to `v2026.7.30` and Bifrost to 1.6.7. `fe10862` moved to
`v2026.8.31` (hermes-agent 0.21.0). `fd5134d` added the dashboard and its
OIDC client.

## Related concepts

- [Bifrost, the model gateway](/components/bifrost.md)
- [The OpenViking service](/components/openviking-service.md)
- [Vault's OIDC provider and its clients](/components/vault-oidc-provider.md)
- [The workload identity chain, as built](/components/workload-identity-chain.md)
- [The host firewall](/components/host-firewall.md)

## Planned, not built

- `hermes-veerle-profile` (planning): Veerle as a second profile in the same
  instance under `gateway.multiplex_profiles`. It waits on three forks. The
  dashboard has no per-profile authorization. The OpenViking memory provider
  reads raw `os.environ`, so it ignores per-profile scoping.
  `var.vault_openviking_workloads` cannot give one job two identity roles.
- `U6-evaluate-hermes-native-secrets` (stub): whether Hermes's own `secrets:`
  config should replace or join the Nomad template injection.
