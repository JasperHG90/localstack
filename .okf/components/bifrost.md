---
type: component
title: Bifrost, the model gateway
description: "How the Bifrost LLM gateway on radxa is wired: provider keys seeded by hand in Vault, native admin auth and enforced virtual keys since B1, keys issued by a Terraform provider that needs a readiness gate, embark as a custom provider, and the ordering, deletion and SSRF traps behind the config."
tags: [bifrost, llm, gateway, virtual-keys, embark, vault, terraform-provider]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: bifrost-jobspec
    resource: git:3ec5d1e:deployments/applications/services/bifrost.hcl
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-providers
    resource: git:3ec5d1e:deployments/applications/providers.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: app-database
    resource: git:3ec5d1e:deployments/applications/database.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: bifrost-smoke
    resource: git:3ec5d1e:scripts/bifrost_smoke.py
  - id: B1-bifrost-native-auth-and-virtual-keys
    resource: loop:B1-bifrost-native-auth-and-virtual-keys
  - id: U5-upgrade-hermes-bifrost-versions
    resource: loop:U5-upgrade-hermes-bifrost-versions
  - id: U7-upgrade-bifrost-2x
    resource: loop:U7-upgrade-bifrost-2x
---

# Bifrost, the model gateway

Bifrost is the one OpenAI-compatible endpoint the cluster's agents call for
chat, embeddings and rerank. It runs as job `bifrost` on `radxa-dragon-q6a`
(192.168.2.50), port 8080, host networking, image
`docker.io/maximhq/bifrost:v2.0.0`. It routes to Ollama Cloud, Gemini and
[embark](/components/embark.md). Hermes and OpenViking run on the same node
and call it at the node address or over loopback. Port 8080 is open to the
whole LAN, and Prometheus dials it directly. The edge serves it as
`bifrost.lab.orangecluster.nl`, and that HAProxy backend carries no basic auth
because Bifrost authenticates its own callers.

## The pieces

| Piece | Where |
|---|---|
| Jobspec, with `config.json` as a template | `deployments/applications/services/bifrost.hcl` |
| Job, readiness gate, virtual keys | `nomad_job.bifrost`, `null_resource.bifrost_ready`, `bifrost_virtual_key.*` in `deployments/applications/services.tf` |
| The Terraform provider | `AirHelp-OSP/bifrost ~>0.1.0` in `deployments/applications/providers.tf` |
| Issued keys under each consumer's prefix | `default/hermes/bifrost`, `default/memex/bifrost`, `default/openviking/bifrost` in `deployments/applications/secrets.tf` |
| embark's key, copied for Bifrost to use | `default/bifrost/embark`, same file |
| Config store database | `bifrost` role and database in `deployments/applications/database.tf`, credential at `default/bifrost/db` |
| Prometheus's copy of the admin login | `default/prometheus/bifrost-admin` in `deployments/infrastructure/secrets.tf` |
| Hand-seeded, not in Terraform | `default/bifrost/ollama-personal`, `ollama-xebia`, `gemini`, `credentials` |
| Firewall | `local.firewall_rules.bifrost` in `deployments/applications/services.tf`: port 8080 open to `192.168.0.0/16` |

## Auth: native admin login and enforced virtual keys

Until B1, HAProxy guarded the edge hostname with `http-request auth` and
Bifrost itself ran open. B1 moved auth into Bifrost:
`governance.auth_config` takes its admin user and password from
`default/bifrost/credentials`, and `client.enforce_auth_on_inference` makes
every inference call present a virtual key. `/health` stays open, which the
readiness gate below relies on. `/metrics` does not, and a path allowlist is
not available, so the service is no longer tagged `prometheus` and Prometheus
scrapes it through a dedicated job carrying basic auth. See
[the observability pipeline](/components/observability-pipeline.md).

The admin login is seeded by hand and read three ways:

- The job renders it into `secrets/bifrost.env` at start.
- The applications root reads it ephemerally to configure the provider.
- The infrastructure root copies it to `default/prometheus/bifrost-admin`
  through a `data` source, not an ephemeral read, because an ephemeral value
  cannot go into `data_json`. That was caught at `terraform validate` in B1.

A rotated seed reaches the job by itself, because the env template re-renders
and restarts the task. Prometheus's copy moves only on an infrastructure apply,
and until then Prometheus scrapes with the old password and reads 401.

## Virtual keys, most of them Terraform resources

`bifrost_virtual_key.hermes`, `.memex` and `.openviking` each allow every model
on every upstream key for the `embark`, `gemini` and `ollama` providers. Each
key's value is set on create, sensitive, and written to a KV secret under its
consumer's own prefix, because the `nomad-workloads` role lets a job read
nothing else. The memex key outlives the commented-out memex job.

Two more live keys, `Leo` and `jasper-laptop-cc`, were made by hand and are not
Terraform resources. Nothing would recreate them, and `terraform plan` cannot
see them go missing. `scripts/bifrost_smoke.py` names them for that reason.

This block has three traps:

- **The provider has no retry.** A key create against a restarting gateway
  gets a 401 or a refused connection. `null_resource.bifrost_ready` polls
  `/health` for up to two minutes, and its triggers carry a hash of the
  jobspec so every Bifrost redeploy re-polls before a key is touched. The
  provider block reads its endpoint from that resource's triggers, which is how
  a provider block, which takes no `depends_on`, is made to wait.
- **`provider_configs` must be alphabetical by `provider`.** The API returns
  the list sorted and the provider models it as ordered, so any other order
  writes the key and then fails the post-apply consistency check.
- **`allowed_models = ["*"]` does not bypass the model catalog.** A model
  Bifrost's catalog lacks is refused as "Model not allowed for this virtual
  key" whatever the allowlist says. The catalog also says nothing about image
  input, which is [Measure a vision model before OpenViking uses
  it](/practices/openviking-vision-models.md).

## Providers and config.json

`config.json` is rendered from the jobspec on every alloc. It is not
authoritative for deletions: `source_of_truth` defaults to `split`, and the
merge keeps any provider key the Postgres store holds that the file omits. A
key dropped from the file keeps routing until it is also deleted with
`DELETE /api/providers/{provider}/keys/{key_id}`. `687ab85` dropped two dead
Ollama keys from the file and recorded that the API delete was still owed, and
that their seeded Vault secrets remain. The config store is Postgres
so virtual keys survive restarts. The logs store is SQLite on the container's
anonymous volume and starts empty on each alloc.

Ollama carries two weighted keys (personal and xebia). Gemini has one, and
consumers address it by the `gemini/` model prefix. embark is a custom
provider with `base_provider_type = "openai"`, pointed at
`http://192.168.2.46:8000`, with only `embedding` and `rerank` allowed so other
request types are refused at the gateway rather than routed to a 404. It needs
`allow_private_network = true`: from 1.5.9 Bifrost refuses RFC1918
destinations, and every other provider is public.

Two gateway behaviors reach past this job:

- Bifrost drops the embeddings `input_type` field, which picks a query prefix
  over a document prefix. That is why [driftwatch](/components/driftwatch.md)
  calls embark directly.
- Through 1.6.11 the rerank endpoint accepted `documents` only as objects and
  answered bare strings with a 400 that names no field. OpenViking sends bare
  strings. 2.0.0 is the first release that accepts them, which is why
  [ADR 0008](/decisions/0008-openviking-rerank-goes-through-bifrost.md) meant an
  upgrade.

## Version history

The pin is `bifrost_version` in `nomad_job.bifrost`. U5 moved it from 1.6.2 to
1.6.7, and U7 moved it to 2.0.0 for the rerank shape. U7 wrote
`scripts/bifrost_smoke.py` to run against both the old and the new gateway. It
asserts inference auth, basic auth on `/metrics`, no open admin path, the
survival of four named virtual keys (`Leo`, `hermes`, `jasper-laptop-cc`,
`memex`, so not `openviking`), and embeddings reaching embark by `routing_info`
rather than by vector length. Its auth probe sends rerank documents as objects,
because at 1.6.7 the payload is parsed before the key is checked, so a
bare-string probe returns 400 and never reaches auth.

## Invariants and what enforces them

| Must stay true | Enforced by |
|---|---|
| Virtual keys are created only against a live gateway | `null_resource.bifrost_ready` |
| `provider_configs` stay alphabetical | the post-apply consistency error |
| Each consumer's key is under its own KV prefix | the `nomad-workloads` role, by refusing anything else |
| Prometheus's admin copy matches the seed | nothing but an infrastructure apply after each rotation |
| A removed provider key stops routing | nothing, so delete it through the API |
| Auth, metrics auth and embark reach hold across upgrades | `scripts/bifrost_smoke.py`, run by hand |
| The hand-made virtual keys still exist | `scripts/bifrost_smoke.py` only |

## Not built

B2 (ready, not started) would put an oauth2-proxy in front of Bifrost's
dashboard and admin API while leaving `/v1/*` on virtual keys. SY1 (planning)
would put NVIDIA's Switchyard in front of Bifrost.

## Related

- [Hermes](/components/hermes.md)
- [The OpenViking service](/components/openviking-service.md)
- [The HAProxy edge](/components/edge-proxy.md)
- [Postgres](/components/postgres.md)
