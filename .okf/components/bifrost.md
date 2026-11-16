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
    resource: deployments/applications/services/bifrost.hcl
  - id: app-services
    resource: deployments/applications/services.tf
  - id: app-providers
    resource: deployments/applications/providers.tf
  - id: app-secrets
    resource: deployments/applications/secrets.tf
  - id: app-database
    resource: deployments/applications/database.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: bifrost-smoke
    resource: scripts/bifrost_smoke.py
---

# Bifrost, the model gateway

Bifrost is the one OpenAI-compatible endpoint the cluster's agents call for
chat, embeddings and rerank. It runs as job `bifrost` on `radxa-dragon-q6a`
(192.168.2.50), port 8080, host networking, image
`docker.io/maximhq/bifrost:v2.3.1`. It routes to Ollama Cloud, Gemini and
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

`bifrost_virtual_key.router` is the one key the Complexity Router reroutes
(see Providers and config.json). It names its four Ollama models,
`clef:27b`, `deepseek-v4.1-flash`, `gpt-oss:120b` and `mistral-large-4`,
because `"*"` admits only catalog models, and allows every Jev model on
`typesafe`. Nothing consumes it yet, so its value is not in Vault.

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

Jev is the built-in `typesafe` provider with no `base_url`: the provider
adds `/v1/systemone` itself, and a non-default base turns off its built-in
model list. Its key comes from `secret/default/bifrost/typesafe`
(`TYPESAFE_API_KEY`), seeded by hand.

The Complexity Router (`governance.complexity_analyzer_config`) grades a chat
with `ollama/clef:27b`, timeout 3 s, and `governance.routing_rules` send
SIMPLE, MEDIUM and COMPLEX to `gpt-oss:120b`, `deepseek-v4.1-flash` and
`mistral-large-4`. Only the `router` key is rerouted: a passthrough rule at
priority 10 lets every other key through before any rule names
`complexity_tier`, so they make no classifier call. The tier rules sit at 11
to 13. The store also holds four global rules made by hand in the admin UI at
priorities 0 to 3, which send Claude Code's `haiku-model`, `sonnet-model`,
`opus-model` and `fable-model` to Ollama models. They run first, they are not
in config.json or Terraform, and a config.json rule that reuses one of their
priorities stops Bifrost at boot (`routing rule with priority 0 already
exists for scope 'global'`, 2026-11-16). A timeout or classifier error leaves
the requested model in place. [ADR 0029](/decisions/0029-bifrost-routes-by-complexity-for-one-virtual-key-and-adds-jev.md)
has the reasons.

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

`bifrost-update` moved the pin to 2.3.1 on 2026-10-20. The 2.1.0 to 2.3.1
config-store migrations cannot be undone (2.3.1 drops columns, 2.3.0 adds a
unique index on `governance_virtual_keys.value_hash`), so the way back to
2.0.0 is restoring the `bifrost` database from the `pg_dumpall` taken just
before the apply. `backup-postgres` names its dumps by date and overwrites
them, so that dump was copied to
`gs://localstack-cluster-backups/postgres-pre-upgrade/bifrost-2.0.0-pgdumpall-2026-10-20.sql.gz`,
a name no job writes. It is a whole-cluster dump, so restore only the
`bifrost` database from it, and the bucket's 180-day rule deletes it on
2027-04-18. 2.1.0 renamed the unknown-key refusal from
`virtual_key_not_found` to `access_not_found`, which the smoke script now
expects. Provider `AirHelp-OSP/bifrost` stays at 0.1.1: keys made on 2.0.0
plan clean after the migration (`spike:bifrost-update/1`, `/4`), and
bare-string rerank still reaches embark unchanged (`spike:bifrost-update/3`).

2.3.1 also checks a key's `allowed_models = ["*"]` against the provider's
model catalog. 2.0.0 passed an unlisted name through to Ollama, which still
served the retired `deepseek-v4-flash:0731`; 2.3.1 refuses it with a 403
("not allowed for virtual key") for every key. A model name must appear in
`GET /v1/models` before a client may use it.

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

Two tickets were planned and never built. B2 would put an oauth2-proxy in
front of Bifrost's dashboard and admin API while leaving `/v1/*` on virtual
keys. SY1 would put NVIDIA's Switchyard in front of Bifrost. Both plans left
the loop when it was reinitialized in `5b2ed1b`, and read from git history
before that commit.

## Related

- [Hermes](/components/hermes.md)
- [The OpenViking service](/components/openviking-service.md)
- [The HAProxy edge](/components/edge-proxy.md)
- [Postgres](/components/postgres.md)

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- loop ticket `B1-bifrost-native-auth-and-virtual-keys` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `U5-upgrade-hermes-bifrost-versions` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `U7-upgrade-bifrost-2x` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
