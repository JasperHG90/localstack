---
epic = "observability"
depends_on = []
priority = 15
summary = """
Route opted-in spans to the LLM backend. The Tempo leg of this shape already
landed in 9767488: the log-shipping Alloy now carries an OTLP receiver and
forwards every span to Tempo. What remains is the second leg, so a service
that declares OTEL_RESOURCE_ATTRIBUTES=trace.sink=llm also reaches Phoenix
(Langfuse Cloud a possible later swap). Additive and reversible; Phoenix
stays deployed.
"""
stub = true
---
# Ticket: O1-observability-otlp-llm-routing

## Already landed (9767488)

Half the shape exists. Tempo sat up for two days holding zero spans, so the
receiver was built ahead of this ticket to make embark traceable at all.

- `otelcol.receiver.otlp` to `otelcol.processor.batch` to
  `otelcol.exporter.otlp` at `192.168.2.47:4317`, in
  `deployments/infrastructure/services/alloy.hcl:161-190`.
- Receiver bound to loopback on `4319`/`4320`, declared as static Nomad ports
  at `alloy.hcl:16-23`.
- embark points at `http://127.0.0.1:4319` and its telemetry is on.
- Measured: five of five Alloy allocations healthy,
  `tempo_receiver_accepted_spans` climbing from zero, and
  `service.name=embark` traces queryable in Grafana by Search and TraceQL.

Two things this settles, and one it does not.

**It answers open question 1 for the Tempo leg, against that question's own
recommendation.** The receiver was folded into the existing `system` job
rather than run as a second, node-constrained job. The Tempo leg wants every
node anyway, since any workload may trace, and it carries no credential, so
the reason for splitting did not apply. The reason still applies to the LLM
leg: an off-site sink's credential has no business on the three nodes that
produce no LLM spans. Question 1 is therefore still open, narrowed to that
leg.

**It makes P8 and P9 binding rather than advisory.** Tempo holds `4317`/`4318`
on rpi5 and Phoenix holds `4317` on orangepi4a. A `system` job claiming the
default ports fails placement on exactly those two nodes and silently stops
shipping their logs, which is why the receiver listens on `4319`/`4320`. Any
LLM-leg collector that also runs as a system job inherits this. One
constrained to LLM nodes does not, since neither of those nodes holds `4317`.

**It does not test the LLM leg.** Nothing has been routed, filtered, or sent
to Phoenix. P1 through P5 still describe untried config, and P12 is still the
risk that decides whether this ticket is worth finishing.

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
- P6 (SUPERSEDED by 9767488): said a second Alloy on the same host needs a
  different `--server.http.listen-addr` and static port. Still true of a
  second job, but no longer describes the tree: the existing `system` job at
  `deployments/infrastructure/services/alloy.hcl` now binds `12345`,
  `4319` and `4320` on every node, and already receives OTLP. A second
  collector must avoid all three.
- P7 (VERIFIED, repo-wide grep): no Nomad node metadata or `node_class`
  exists. Every constraint in the repo is `attr.unique.hostname` against a
  literal (e.g. `deployments/applications/services/phoenix.hcl:6-9`).
  Selecting two nodes means `set_contains_any`, not invented node meta.
- P8 (VERIFIED, `deployments/applications/services/phoenix.hcl:16` and
  `:6-9`): Phoenix binds `4317` on `orangepi4a`. That node runs no LLM
  producer, so placing the collector there would collide for no benefit.
  Confirmed the hard way in 9767488: a `system` job cannot use `4317` at
  all, because of this node and rpi5.
- P9 (VERIFIED, `deployments/applications/services/tempo.hcl:22-26`):
  Tempo's OTLP receivers are `4317` (gRPC) and `4318` (HTTP) on
  `192.168.2.47`.
- P10 (VERIFIED, Langfuse docs): Langfuse Cloud is OTLP over HTTP only, no
  gRPC. Endpoint `/api/public/otel`, Basic auth `base64(pk:sk)`, header
  `x-langfuse-ingestion-version: 4`. Understands OpenInference, which memex
  already emits. A Langfuse leg must therefore be
  `otelcol.exporter.otlphttp`, not `otelcol.exporter.otlp`.
- P11 (UNVERIFIED, anchor refreshed to
  `deployments/applications/services.tf:44-53`): that the LAN-wide `4317`
  rule on Phoenix's host is sufficient for cross-node export. The rule is
  read, not probed. Verify before assuming no firewall change. Note the
  Tempo leg needed no firewall work at all, because the receiver is on
  loopback and Tempo's own rules already admitted every node; an LLM leg
  crossing to `orangepi4a` is the first part of this shape that leaves a
  node.
- P12 (UNVERIFIED): that Phoenix renders collector-forwarded spans
  identically to SDK-direct ones — i.e. that batching through Alloy
  preserves the resource and OpenInference attributes Phoenix keys its UI
  on. Nothing in this session tested Phoenix ingest.
- P13 (UNVERIFIED): the granularity consequence. `OTEL_RESOURCE_ATTRIBUTES`
  is per-process, so tagging memex sends its Postgres and HTTP spans to the
  LLM backend too, not just model calls. Harmless for self-hosted Phoenix;
  a billing question for a metered sink.
- P14 (RESOLVED, and the list moved): the LLM producers are not what this
  premise assumed. memex is commented out in
  `deployments/applications/services.tf` and no longer runs on
  `jetson-orin-nano`, so the one service that actually exported to Phoenix
  is down and Phoenix is idle. embark took that node and traces today, but
  it serves embeddings and reranking, so whether its spans belong in an LLM
  backend is a judgment this ticket has to make rather than inherit. Settle
  the producer list against the running cluster at flesh-out, not against
  this line.

## Non-goals

- NOT removing Phoenix. Phoenix stays deployed and running; this ticket is
  additive and reversible. Teardown is a separate decision.
- NOT adding Langfuse Cloud. P10 is recorded so the design does not
  foreclose it, but no off-site sink, no Vault credential, and no `vault {}`
  block on the collector in this ticket.
- NOT touching the existing log-shipping Alloy job's log pipeline.
- NOT adding an OTLP receiver on non-LLM nodes. Superseded by 9767488: the
  receiver is on every node already, because the Tempo leg wants it there.
  Read this as "no LLM-leg exporter on non-LLM nodes".
- NOT instrumenting any application. Producers already emit OTLP.
- NOT metrics or logs over OTLP. Traces only.

## Open questions

1. **One collector job or fold into the existing Alloy?** ANSWERED for the
   Tempo leg, STILL OPEN for the LLM leg. 9767488 folded the receiver into
   the `system` job: every node may produce spans and the Tempo leg carries
   no credential, so the reason to split did not apply. It does apply to the
   LLM leg. Recommendation unchanged there: a SEPARATE job constrained to the
   LLM nodes, so an off-site credential stays off the nodes that produce no
   LLM spans. Note that job must avoid `12345`, `4319` and `4320` as well as
   `4317`, since the system job now holds all three on every node.
2. **Which Terraform root?** SETTLED by precedent: `deployments/infrastructure`,
   which is where the receiver landed, next to `alloy.hcl`. It needs no MinIO
   bucket creds, the rule that pushed Loki and Tempo into the applications
   root.
3. **Do memex's non-LLM spans belong in Phoenix?** (from P13)
   Recommendation: accept them for now — Phoenix is self-hosted and the
   extra context is useful. Revisit only if a metered sink is added, at
   which point narrow with a second span-level condition
   (`openinference.span.kind`) applied ONLY to services that already opted
   in. Narrowing must never become part of deciding participation.
4. **Which services emit OTLP at all today?** Only embark, verified: it is
   the sole value of `service.name` in Tempo. memex is configured for it
   (`memex.hcl:163`) but is commented out and not running. hermes is still
   unverified. A `trace.sink` env var on a service that emits nothing is
   inert, which is harmless but should be stated rather than assumed.

5. **Does the LLM leg still have a producer?** New, and it decides whether
   this ticket is worth finishing now. memex was the only service that ever
   sent spans to Phoenix, and it is down. embark serves embeddings and
   reranking rather than completions, so calling its spans LLM traffic is a
   judgment, not a given. If the answer is "no producer today", the honest
   move is to leave the Tempo leg as the whole of the shape and revisit when
   memex returns or hermes is instrumented.
6. **Fallback if P12 fails.** If Phoenix renders forwarded spans worse than
   direct ones, options: keep memex pointed directly at Phoenix and use the
   collector for Tempo only, or drop the batch processor on the LLM leg.
   Recommendation: settle by probe during flesh-out, before writing the
   jobspec.

## Premises / assumptions

See "Vision & rough premises" above, P1-P14. P1-P5, P7, P9 and P10 are
verified and untouched by 9767488. P6 is superseded and P14 is resolved
against a cluster that has since changed. P8 was verified twice, the second
time by hitting it. P11, P12 and P13 remain unverified and must be settled
during flesh-out; P12 is the one that decides whether the LLM leg works at
all.
