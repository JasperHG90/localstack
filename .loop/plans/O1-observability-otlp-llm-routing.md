---
epic = "observability"
depends_on = []
priority = 15
summary = """
Put a per-node Alloy OTLP collector in front of the trace backends so apps
emit once: everything to Tempo, and only services that opt in with
OTEL_RESOURCE_ATTRIBUTES=trace.sink=llm also reach the LLM backend (Phoenix
today, Langfuse Cloud a possible later swap). Additive and reversible;
Phoenix stays deployed.
"""
stub = true
---
# Ticket: O1-observability-otlp-llm-routing

## Triggered by

Tempo landed in `9a84f24` with no collector in the path, so every producer
points straight at one backend: memex hardcodes Phoenix
(`deployments/applications/services/memex.hcl:163`). Operator wants the
option to move LLM tracing off-box (Langfuse Cloud) without redeploying
every producer, and wants opt-in to be declared by the workload, not
inferred by the collector.

## Vision & rough premises

Shape: `app --OTLP--> Alloy (LLM nodes only) --> Tempo (all spans)`
and `--> LLM backend (opted-in spans only)`.

The collector becomes the seam. Swapping Phoenix for Langfuse later is a
collector config change, not a producer redeploy.

- P1 (VERIFIED, `alloy validate` against `grafana/alloy:v1.19.2`):
  `otelcol.connector.routing` does NOT exist in Alloy. Error: `cannot find
  the definition of component name "otelcol.connector.routing"`. Routing
  must be composed from `otelcol.processor.filter` branches, one per
  destination. Ugly beyond ~3 sinks.
- P2 (VERIFIED, same probe): `otelcol.exporter.debug` does NOT exist in
  Alloy either. Testing a pipeline needs real HTTP sinks.
- P3 (VERIFIED end-to-end against `grafana/alloy:v1.19.2`): opt-in routing
  works and absence is the safe default. Config
  `span = ["resource.attributes[\"trace.sink\"] != \"llm\""]` in
  `otelcol.processor.filter`. Two spans posted to the receiver; two local
  HTTP sinks recorded what arrived. Untagged span (`plain-service`) reached
  the Tempo leg only. Tagged span (`llm-service`, resource attr
  `trace.sink=llm`) reached both legs. Tempo leg: 2 requests. LLM leg: 1.
- P4 (VERIFIED, follows from P3): `otelcol.processor.filter` DROPS what
  matches, so the opt-in expression is a negation. A service that declares
  nothing has a nil attribute, and `nil != "llm"` is true, so it is dropped
  from the LLM leg. Inverting this expression silently ships every service
  to the LLM sink and makes opt-OUT mandatory — the exact failure this
  ticket exists to prevent.
- P5 (VERIFIED, docs + P3): `error_mode = "ignore"` is required so a
  missing attribute fails the comparison rather than erroring the batch.
- P6 (VERIFIED, `deployments/infrastructure/services/alloy.hcl:3,9,36`):
  the existing log-shipping Alloy is a `system` job binding `12345` on
  every node. A second Alloy on the same host needs a different
  `--server.http.listen-addr` and a different static port.
- P7 (VERIFIED, repo-wide grep): no Nomad node metadata or `node_class`
  exists. Every constraint in the repo is `attr.unique.hostname` against a
  literal (e.g. `deployments/applications/services/phoenix.hcl:6-9`).
  Selecting two nodes means `set_contains_any`, not invented node meta.
- P8 (VERIFIED, `deployments/applications/services/phoenix.hcl:16` and
  `:6-9`): Phoenix binds `4317` on `orangepi4a`. That node runs no LLM
  producer, so placing the collector there would collide for no benefit.
- P9 (VERIFIED, `deployments/applications/services/tempo.hcl:22-26`):
  Tempo's OTLP receivers are `4317` (gRPC) and `4318` (HTTP) on
  `192.168.2.47`.
- P10 (VERIFIED, Langfuse docs): Langfuse Cloud is OTLP over HTTP only, no
  gRPC. Endpoint `/api/public/otel`, Basic auth `base64(pk:sk)`, header
  `x-langfuse-ingestion-version: 4`. Understands OpenInference, which memex
  already emits. A Langfuse leg must therefore be
  `otelcol.exporter.otlphttp`, not `otelcol.exporter.otlp`.
- P11 (UNVERIFIED): that
  `deployments/applications/services.tf:45-52`'s LAN-wide `4317` rule is
  sufficient for cross-node export to Phoenix. The rule is read, not
  probed. Verify before assuming no firewall change.
- P12 (UNVERIFIED): that Phoenix renders collector-forwarded spans
  identically to SDK-direct ones — i.e. that batching through Alloy
  preserves the resource and OpenInference attributes Phoenix keys its UI
  on. Nothing in this session tested Phoenix ingest.
- P13 (UNVERIFIED): the granularity consequence. `OTEL_RESOURCE_ATTRIBUTES`
  is per-process, so tagging memex sends its Postgres and HTTP spans to the
  LLM backend too, not just model calls. Harmless for self-hosted Phoenix;
  a billing question for a metered sink.
- P14 (UNVERIFIED): which nodes are LLM producers at implementation time.
  Today: `jetson-orin-nano` (memex) and `radxa-dragon-q6a` (hermes,
  bifrost). Adding embark may add a third.

## Non-goals

- NOT removing Phoenix. Phoenix stays deployed and running; this ticket is
  additive and reversible. Teardown is a separate decision.
- NOT adding Langfuse Cloud. P10 is recorded so the design does not
  foreclose it, but no off-site sink, no Vault credential, and no `vault {}`
  block on the collector in this ticket.
- NOT touching the existing log-shipping Alloy job's log pipeline.
- NOT adding an OTLP receiver on non-LLM nodes.
- NOT instrumenting any application. Producers already emit OTLP.
- NOT metrics or logs over OTLP. Traces only.

## Open questions

1. **One collector job or fold into the existing Alloy?** Recommendation: a
   SEPARATE job constrained to the LLM nodes. The log shipper must stay a
   `system` job on all five; the collector must not. One job cannot be both,
   and splitting keeps any future off-site credential off the three nodes
   that have no reason to hold it.
2. **Which Terraform root?** Recommendation: `deployments/infrastructure`,
   next to the existing `alloy.hcl`. It needs no MinIO bucket creds, which
   is the rule that pushed Loki and Tempo into the applications root.
3. **Do memex's non-LLM spans belong in Phoenix?** (from P13)
   Recommendation: accept them for now — Phoenix is self-hosted and the
   extra context is useful. Revisit only if a metered sink is added, at
   which point narrow with a second span-level condition
   (`openinference.span.kind`) applied ONLY to services that already opted
   in. Narrowing must never become part of deciding participation.
4. **Does hermes emit OTLP at all today?** Unverified. memex does
   (`memex.hcl:163`). If hermes does not, the `trace.sink` env var on it is
   inert until it is instrumented, which is harmless but should be stated
   rather than assumed.
5. **Fallback if P12 fails.** If Phoenix renders forwarded spans worse than
   direct ones, options: keep memex pointed directly at Phoenix and use the
   collector for Tempo only, or drop the batch processor on the LLM leg.
   Recommendation: settle by probe during flesh-out, before writing the
   jobspec.

## Premises / assumptions

See "Vision & rough premises" above — P1-P14. P1-P10 are verified, P11-P14
are not and must be settled during flesh-out.
