---
type: architecture
title: The three deployment layers
description: "The cluster is deployed in three layers applied in order: Ansible under bootstrap/, then the Terraform root deployments/infrastructure, then deployments/applications. Says what each layer owns, the rule behind each boundary, how a later layer finds what an earlier one made without any state link, what breaks when the order is broken, and which file a new node, job, Vault role, bucket, port or HashiStack setting goes in."
tags: [architecture, ansible, terraform, bootstrap, vault, consul, nomad, apply-order]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: bootstrap-justfile
    resource: git:73742f6:bootstrap/justfile
  - id: enable-consul-secrets
    resource: git:73742f6:bootstrap/playbooks/enable_consul_secrets.yml
  - id: nomad-server-tasks
    resource: git:73742f6:bootstrap/roles/nomad_server/tasks/main.yml
  - id: configure-network
    resource: git:73742f6:bootstrap/playbooks/configure_network.yml
  - id: infra-services
    resource: git:73742f6:deployments/infrastructure/services.tf
  - id: infra-identity
    resource: git:73742f6:deployments/infrastructure/identity.tf
  - id: infra-machine-roles
    resource: git:73742f6:deployments/infrastructure/machine_roles.tf
  - id: infra-oidc
    resource: git:73742f6:deployments/infrastructure/oidc.tf
  - id: infra-secrets
    resource: git:73742f6:deployments/infrastructure/secrets.tf
  - id: apps-providers
    resource: git:73742f6:deployments/applications/providers.tf
  - id: apps-services
    resource: git:73742f6:deployments/applications/services.tf
  - id: apps-justfile
    resource: git:73742f6:deployments/applications/justfile
  - id: readme
    resource: git:73742f6:README.md
  - id: roots-split-commit
    resource: git:f76edbe
  - id: F5-foundation-vault-nomad-secrets-engine
    resource: loop:F5-foundation-vault-nomad-secrets-engine
  - id: F6-foundation-vault-consul-secrets-engine
    resource: loop:F6-foundation-vault-consul-secrets-engine
  - id: G2-nomad-ui-oidc-login
    resource: loop:G2-nomad-ui-oidc-login
---

# The three deployment layers

Three layers deploy this cluster, and each is applied before the next:

1. **Ansible** (`bootstrap/`) turns five hosts into a Consul, Vault and Nomad
   cluster and hands Vault the credentials it brokers from.
2. **The infrastructure root** (`deployments/infrastructure`) configures Vault
   and runs the shared services every application uses.
3. **The applications root** (`deployments/applications`) runs the workloads
   and the buckets, databases and secrets they own.

No layer reads another's state. A later layer finds what an earlier one made by
a fixed name in Vault, the Consul catalog, or Nomad, or by a literal someone
kept equal by hand. That is why the order is fixed and why most cross-layer
mistakes show up as a denied read or an unplaceable job at apply or run time.

This page is the map of the boundaries. The inside of each layer is in
[the Ansible bootstrap](/components/bootstrap.md) and [the two Terraform
roots](/components/terraform-roots.md). How the `.tf` files within a root are
split is `.claude/rules/terraform-file-layout.md`.

## What each layer owns

| Layer | Owns | Does not own |
|---|---|---|
| Ansible | packages and HashiStack versions (`bootstrap/inventory/group_vars/all.yml`), every Consul, Vault and Nomad config file, Consul ACL bootstrap, Vault init and unseal, Nomad ACL bootstrap, the Consul ACL policies and tokens Vault and Nomad use to reach Consul, the Nomad `developer` ACL policy, the `jwt-nomad` auth mount with its default role and the shared `nomad-workloads` policy, the `nomad/` and `consul/` engine mounts and their `config/access`, the Consul `deploy` ACL policy, the `bootstrap/` KV mount and its two secrets, Podman, the NVIDIA runtime, Tailscale, and ufw's default policy plus the HashiStack ports | any Nomad job, any Vault policy other than `nomad-workloads` |
| Infrastructure root | the `secret` KV mount, human auth (`userpass`, `jwt-lab`), identity, groups and human policies (`identity.tf`), the OIDC provider, every client and the Nomad OIDC auth method (`oidc.tf`), the Nomad and Consul engine roles, the Nomad `deploy` and `dash_read` ACL policies, the per-job JWT roles and their policies (`machine_roles.tf`), the `redis/` database engine (`database.tf`), all fourteen host volumes, the shared jobs (postgres, minio, haproxy, acme, prometheus, grafana, alloy, node-exporter, the two oauth2-proxy jobs, nats, redis, two backup jobs), their KV secrets and firewall rules, and the GCS backup bucket | MinIO buckets, Postgres roles and databases, application jobs |
| Applications root | the application jobs (hermes, loki, tempo, registry, embark, openviking, ov-dash, driftwatch, dash, registry-ui, bifrost), their MinIO buckets, IAM and access keys (`storage.tf`), Postgres roles, databases and grants (`database.tf`), their KV secrets (`secrets.tf`), the Bifrost virtual keys, and their firewall rules | any Vault mount, auth method, policy or role, any host volume |

Four placements surprise a first reader:

- **Host volumes are all in infrastructure**, including eight reserved
  for application jobs, seven of them mounted today (memex's job is commented
  out). [Host volumes](/components/host-volumes.md) has the
  table and the node-pinning trap.
- **Observability is split across the two roots.** Prometheus, Grafana, Alloy
  and node-exporter are infrastructure jobs. Loki and Tempo are application
  jobs, because their MinIO buckets are applications' (the comment above
  `nomad_job.alloy`, `deployments/infrastructure/services.tf:573-576`).
  Grafana and Alloy then reach Loki and Tempo by literal address
  (`deployments/infrastructure/services/grafana.hcl:139,171`,
  `deployments/infrastructure/services/alloy.hcl:75`).
- **The edge routes to applications from infrastructure.** HAProxy's backends
  are literals in `deployments/infrastructure/services/haproxy.hcl`, so
  putting an application behind the edge is an infrastructure change.
- **Vault policy is split between Ansible and Terraform.** Ansible writes
  `nomad-workloads`, which every workload uses. Terraform writes every other
  Vault policy, including the per-job policies attached beside it.

The applications root writes only KV values into Vault. It creates no mount,
auth method, policy or role, so every Vault permission a job needs exists
before the job is submitted.

## Why the lines are drawn where they are

### Ansible and Terraform: who holds a bootstrap credential

The stated rule is in the header of
`bootstrap/playbooks/enable_consul_secrets.yml:1-8`, which calls it the
config-split invariant: work that needs the Consul management token stays in
Ansible, and Terraform owns only the Vault role that names the policy. F5 set
it up for Nomad and F6 copied it for Consul.

As the code stands, the rule is narrower than "no management token in
Terraform". What Ansible keeps to itself are the three bootstrap credentials,
all on the manager: Vault's root token in `/opt/vault/init.json`, Consul's
bootstrap token in `/opt/consul/bootstrap_token`, and Nomad's in
`/opt/nomad/init.json`. Anything that must be written with one of them is
Ansible's. Terraform works only with what Vault brokers, and since G2 that
includes a 30-minute Nomad management token, read every run through
`provider "nomad" { alias = "manage" }`
(`deployments/infrastructure/machine_roles.tf:58-66`). G2's plan names the
cost: anyone holding `developer` can mint that token.

This corrects the wording in [Vault's dynamic secrets
engines](/components/vault-secrets-engines.md#who-owns-what), which says a
Nomad or Consul management token never reaches Terraform. That page has why
the Consul `deploy` policy stayed in Ansible while Nomad ACL policies moved to
Terraform. A brokered Consul management token, the shape G2 used for Nomad, was
never tried.

Two Ansible holdings follow a different reason. The `jwt-nomad` mount is
configured with a JWKS URL on the manager's loopback, and the shared policy
embeds that mount's accessor when it renders
([the workload identity chain](/components/workload-identity-chain.md)). The
role that configures the Nomad server sets them up together. No comment gives
a reason beyond that. Terraform already writes roles on the mount, under the
`developer` grant on `auth/jwt-nomad/role/*`
(`deployments/infrastructure/identity.tf:442`).

### Infrastructure and applications: what a provider needs to exist

No comment or ticket states this rule. It is inferred from the code and from
the history: the commit that split the roots (`f76edbe`, 2025-10-31) put
Postgres in infrastructure, and `1855ed9` added MinIO there a day later,
together with a registry that an applications job later replaced.

The applications root configures three providers from services that must
already be running: `minio` and `postgresql` from the Consul catalog and an
admin credential in KV, and `bifrost` from its own job
(`deployments/applications/providers.tf:44-69`). The `minio` and `postgresql`
providers are fed by data-source and ephemeral reads that run at plan time
with no dependency edge (`deployments/applications/services.tf:1-19`), so
their services must already be running when the plan starts. So:

- a service that applications' providers log into belongs in infrastructure
  (postgres, minio), and so does a service an infrastructure Vault engine
  connects to during apply (redis, `deployments/infrastructure/database.tf`)
- anything written through those providers belongs in applications: buckets,
  IAM, Postgres roles and databases, Bifrost keys
- a job that needs one of those objects follows it into applications, which is
  why Loki and Tempo are not beside Prometheus

On top of that, infrastructure holds all Vault configuration and the shared
plumbing an application would otherwise rebuild (the edge, metrics, NATS,
backups, host volumes). Bifrost shows the other way to do it: its provider is
in the same root as its job and waits on it through a resource reference to
`null_resource.bifrost_ready`, because provider blocks take no `depends_on`.
That works, and was not used for MinIO or Postgres.

## How a later layer finds an earlier one

There is no `terraform_remote_state` in the repo, and Terraform never reads
Ansible's output. Every handoff is a name.

| What crosses | From, to | Channel |
|---|---|---|
| Nomad and Consul deploy tokens | Ansible engine mounts plus infrastructure `machine_roles.tf` roles, both roots | `nomad/creds/deploy`, `consul/creds/deploy`, exported by `localstack env` |
| Nomad management token | Ansible engine, infrastructure | `nomad/creds/manage` through the `nomad.manage` alias |
| Nomad `developer` ACL policy | Ansible, infrastructure | referenced by name in `nomad_acl_binding_rule.developer` (`deployments/infrastructure/oidc.tf:423-435`) |
| Consul `deploy` ACL policy | Ansible, infrastructure | `consul_policies = ["deploy"]` in `machine_roles.tf` |
| `nomad-workloads` role and policy | Ansible, both roots' jobs | every per-job JWT role repeats both policy names and the claim mappings |
| MinIO and Postgres addresses | infrastructure jobs, applications | `data "consul_service"` for `minio` and `postgres-db`, which the Consul `deploy` policy allows by name (`bootstrap/playbooks/enable_consul_secrets.yml:49-57`) |
| MinIO and Postgres admin credentials | infrastructure `secrets.tf`, applications | `ephemeral "vault_kv_secret_v2"` at `default/minio/localstack` and `default/postgres/localstack` |
| OIDC client ids | infrastructure `oidc.tf`, applications | `data "vault_identity_oidc_client_creds"` for `memex` and `hermes-dashboard` (`deployments/applications/services.tf:34-46`) |
| Host volumes and JWT roles | infrastructure, applications jobs | the name in the jobspec |
| Loki, Tempo, dash, registry-ui, every edge backend | applications, infrastructure jobs | literal addresses in infrastructure jobspecs |

The literals kept equal by hand, each guarded only by a comment beside it, are
listed in [the two Terraform
roots](/components/terraform-roots.md#how-applications-reads-infrastructure).
The pattern to take from them: a name crossing a layer boundary has no check,
so a rename on one side is found at login or placement time on the other.

## Apply order

Ansible, then infrastructure, then applications. `just bootstrap` runs the nine
playbooks in the order `bootstrap/justfile:40-49` lists them, and `README.md`
gives the three layers in that order. What goes wrong out of order:

| Broken order | Symptom |
|---|---|
| Terraform before Ansible | no Consul, Vault or Nomad to talk to, and no engine mounts |
| applications before infrastructure | provider setup fails before any resource when MinIO or Postgres is missing from the catalog or their admin KV is missing. The OIDC client reads then fail at refresh. `localstack login` also fails, because its roles and policy are infrastructure's. |
| a job before its host volume | the job cannot be placed |
| a job before its JWT role | the task cannot log in to Vault |
| an application behind the edge before its HAProxy route | the hostname answers with no backend |
| a new `data "consul_service"` before the Consul `deploy` policy names it | the read is denied until `enable_consul_secrets.yml` gains a line and is re-run |
| a new Vault mount before `developer` grants it | 403 at apply, which is why `vault_mount.redis` carries `depends_on = [vault_policy.developer]` (`deployments/infrastructure/database.tf:39`) |

**Day 0.** The first infrastructure apply cannot run on a `localstack login`
session, because that session needs the `userpass` mount, the `developer`
policy and group (`deployments/infrastructure/identity.tf:21,346,510`) and the
`deploy` and `manage` broker roles (`machine_roles.tf:18,125,152`), all created
by that same apply. After Ansible the engines are mounted but mint nothing. So
the first run uses the Vault root token and the Nomad and Consul bootstrap
tokens from the manager (`/opt/vault/init.json`, `/opt/nomad/init.json`,
`/opt/consul/bootstrap_token`). No runbook in the repo writes this down.

An empty cluster also needs hand-seeded KV that no layer writes:
`default/bifrost/credentials` and the other Bifrost and Hermes secrets listed
in [the two Terraform roots](/components/terraform-roots.md#apply-order).
Infrastructure reads `default/bifrost/credentials` with a data source
(`deployments/infrastructure/secrets.tf:133-136`) from the `secret` mount the
same root creates, so the first plan cannot succeed in one pass. No runbook
writes the workaround down.

**Day 2.** Most changes touch one layer. Three do not:

- Re-running all of `just bootstrap` also runs `seed_vault.yml`, which resets
  the bootstrap secrets from the environment. Run single playbooks instead
  ([the Ansible bootstrap](/components/bootstrap.md#day-0-and-day-2)).
- Recreating the `jwt-nomad` mount changes its accessor, so the shared policy
  must be rendered again by Ansible before any workload can read.
- Rotating the Bifrost admin password needs an infrastructure apply, which
  copies it into Prometheus's prefix
  (`deployments/infrastructure/secrets.tf:124-129`).

## Credentials each layer runs with

| Layer | Runs as |
|---|---|
| Ansible | SSH with `.ssh/id_rsa` and sudo (`bootstrap/ansible.cfg`). On the manager it reads the three bootstrap credentials from disk. On day 0 it reads GitHub and Tailscale secrets from the environment. |
| Infrastructure | Day 0: the bootstrap tokens (see above). Day 2: the operator's `localstack login` session: `VAULT_TOKEN` carrying `developer`, a brokered Nomad deploy token and a brokered Consul token. A fresh brokered Nomad management token per run. `.ssh/id_rsa` for the ufw `null_resource`. gcloud credentials for the `google` provider. |
| Applications | The same session. MinIO, Postgres and Bifrost admin credentials read ephemerally from KV. `.ssh/id_rsa` for its ufw `null_resource`. |

Neither root has an identity of its own. Why the per-root deployers were
dropped, and what `developer` can reach, is [Terraform deployer
credentials](/components/deployer-credentials.md).

## Where a new thing goes

| New thing | Layer and file |
|---|---|
| Node | Ansible: `bootstrap/inventory/cluster.ini`, then the playbooks. Terraform refers to nodes by literal hostname and address, so each job and volume placed there names it too. See [Node placement](/nodes/placement.md). |
| HashiStack version | Ansible: `bootstrap/inventory/group_vars/all.yml`, one at a time |
| HashiStack setting | Ansible: the template in `bootstrap/roles/<role>/templates/`, then re-run that role's playbook |
| Port for Consul, Vault or Nomad themselves | Ansible: `bootstrap/playbooks/configure_network.yml` |
| Port for a job | the `local.firewall_rules` map in the `services.tf` of the root that runs the job ([the host firewall](/components/host-firewall.md)). Removing an entry closes nothing. |
| Application job | applications `services.tf`, with its jobspec under `deployments/applications/services/` |
| Shared service that applications' providers or an infrastructure Vault engine connect to | infrastructure `services.tf` |
| Host volume for any job | infrastructure `services.tf`, `### Dynamic Host Volumes` |
| Edge route | infrastructure `services/haproxy.hcl` (`docs/how-to/add-a-service-to-the-edge.md`) |
| KV secret for an application | applications `secrets.tf`, under `default/<job>/` so `nomad-workloads` lets the job read it |
| KV secret for an infrastructure job | infrastructure `secrets.tf` |
| JWT role for a job needing more than its own KV prefix | infrastructure `machine_roles.tf` ([ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md)) |
| Human auth method, group, or human policy | infrastructure `identity.tf` (a per-job policy goes in `machine_roles.tf`) |
| OIDC client | infrastructure `oidc.tf` (`docs/how-to/add-a-vault-oidc-client.md`) |
| Vault secrets engine | infrastructure, with an exact `sys/mounts/<path>` grant added to `developer` in `identity.tf` first. If configuring it needs a bootstrap credential, Ansible instead. |
| MinIO bucket or IAM | applications `storage.tf` and `deployments/applications/modules/bucket/` |
| Postgres role or database | applications `database.tf` |
| Consul catalog lookup from Terraform | a `service` line in `bootstrap/playbooks/enable_consul_secrets.yml` first |

## Known exceptions and drift

- **Three applications recipes lose the session.** `init`, `destroy` and
  `state_rm` (`deployments/applications/justfile:9-31`) run without the
  `localstack env` exports. The detail is in [Terraform deployer
  credentials](/components/deployer-credentials.md#what-a-run-authenticates-with).
- **`README.md:24` puts the registry in infrastructure.** It is an application
  job (`nomad_job.registry`, `deployments/applications/services.tf:383`).
- **`README.md:51-59` runs `just init` in applications**, which is one of the
  recipes above.
- **`developer` names no path under `jwt-lab`.** The infrastructure root
  manages `vault_jwt_auth_backend.lab` and its `ov_dash` role
  (`deployments/infrastructure/identity.tf:246,271`). The policy's auth grants
  stop at `sys/auth/userpass` and `auth/jwt-nomad/role/*`
  (`deployments/infrastructure/identity.tf:393,442`). Refreshing the role reads
  `auth/jwt-lab/role/ov-dash`, so a plan run on `developer` alone should be
  denied there, and changing either likely needs the `admin` group. Not
  measured.
- **Comments still describe the pre-session credentials**, in
  `machine_roles.tf` and `oidc.tf`. [Terraform deployer
  credentials](/components/deployer-credentials.md#what-f8-still-owns) lists
  them.
- **The firewall writers do not converge.** Three layers add ufw rules and none
  removes one, and the two roots re-run theirs on different triggers
  ([the host firewall](/components/host-firewall.md)).
