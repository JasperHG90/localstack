# Monitoring stack

## Who can reach the monitoring stack

Prometheus, Loki and Tempo are reachable only from inside the cluster. All
three serve their query APIs with no authentication, so there are two barriers
rather than one: their firewall rules admit only the callers that need them,
and none is routed through the edge proxy. Going to `192.168.2.47:9090`,
`192.168.2.47:3100` or `192.168.2.47:3200` from an ordinary LAN device fails,
and so does asking HAProxy for them.

**You read all three through Grafana.** Its Explore view queries the
Prometheus, Loki and Tempo datasources, which dial `192.168.2.47` directly
from the same node. Grafana requires a login, so it is the authenticated front
door to data that has no authentication of its own. That login is Vault SSO.
See [How to sign in to Grafana](../how-to/sign-in-to-grafana.md).

| Service | Port | Who may connect |
|---|---|---|
| Prometheus | 9090 | `192.168.2.47` only, which is Grafana's datasource on the same node |
| Loki | 3100 | all five node addresses, because Alloy is a `system` job and ships from every node |
| Tempo | 3200 | `192.168.2.47` (Grafana) and `192.168.2.30` (the edge) |
| Tempo OTLP | 4317, 4318 | all five node addresses, since any workload may export traces |
| Grafana | 3000 | `192.168.0.0/16` and `100.64.0.0/10`, unchanged |

Grafana is unchanged. It requires a login, so it keeps its LAN and tailnet
reach on port 3000.

Prometheus scraping is unaffected. It dials outward to its targets, and no
inbound rule touches that.

Why none of them is routed through the edge proxy is in
[Why monitoring is not behind the edge](../explanation/why-monitoring-is-not-behind-the-edge.md).
To reach Prometheus or Loki without Grafana, see
[How to reach Prometheus or Loki directly](../how-to/reach-prometheus-or-loki-directly.md).

## Retrieval quality has its own page

Three dashboards cover the retrieval stack: `/d/localstack-embark` for the
models, `/d/localstack-openviking` for live retrieval, and
`/d/localstack-retrieval-quality` for whether the models are still as good as
they were. The last one reads `driftwatch`, a daily canary, and the alerts
that go with it are the `retrieval-quality` group in `alert-rules.yaml`.

How to read them is in [Retrieval quality](retrieval-quality.md), and what to
do when one fires is in
[How to respond to a retrieval-quality alert](../how-to/respond-to-a-retrieval-quality-alert.md).

## Where alerts go

Grafana sends every alert to one Telegram chat: the operator's private chat
with **OrangeClusterAlertBot**. The contact point is provisioned from
`services/grafana.hcl`, which reads the bot token from Vault KV2 at
`default/grafana/telegram` and the chat id from the `telegram_alert_chat_id`
variable.

Hermes uses a different bot, **@OrangeHermes**, with a different token, at
`default/hermes/telegram`. Terraform writes neither value. Both are
hand-managed in Vault, so pointing alerts at another bot means editing the
Vault secret, and no `terraform apply` takes part in it. Grafana picks the new
token up by itself: the contact point template renders it straight from Vault
and restarts the task when it changes.

Two separate things scope this bot, and each has its own enforcer.

**Outbound is the chat id.** Grafana writes to that one chat and nowhere else,
so nobody but the operator ever receives an alert. This is the half the repo
controls, and it is one line of the contact point.

**Inbound is the missing listener.** Nothing calls `getUpdates` and no webhook
is registered for this token, so anything sent to the bot is read by nothing.
Anyone who knows the bot's @username can still open a chat and type at it.
BotFather has no setting that stops them: Telegram's bot documentation states
that all bots must be able to process direct messages. What BotFather does
control is groups, and group joins were turned off on 2026-09-06, so the bot
cannot be added anywhere the operator did not put it. Nothing in this repo can
notice that setting being flipped back, so check BotFather rather than trust
this line.

One more condition decides whether anything arrives at all.

**A bot cannot start a conversation, so you must message it first.** A new
alert bot delivers nothing until the operator presses Start on it. At Grafana's
default `info` level the log reads `failed to send telegram message: webhook
response status 403 Forbidden`. Telegram's own explanation, `bot can't initiate
conversation with a user`, rides in the response body and reaches the log only
at `debug`. Alerts fire normally in the UI and nothing arrives. This is the
step the next bot swap will trip over.

## Sending traces

Tempo stores traces. Point an OpenTelemetry SDK at it and traces show up in
Grafana's Tempo datasource:

```
OTEL_EXPORTER_OTLP_ENDPOINT=http://192.168.2.47:4317   # gRPC
OTEL_EXPORTER_OTLP_ENDPOINT=http://192.168.2.47:4318   # HTTP
```

There is no collector in between. Apps speak OTLP straight to Tempo, the same
way they log to stdout and let Alloy pick it up. Alloy runs on every node but
handles logs only, so adding an OTLP hop there is a later change, not a
prerequisite.

Traces and logs cross-link in both directions once an app emits a `trace_id`
on its log lines:

- From a log line to the trace: Grafana's Loki datasource reads `trace_id`
  from structured metadata and renders it as a link into Tempo. Loki attaches
  that metadata itself for logs ingested over OTLP.
- From a span to the logs: the Tempo datasource's trace-to-logs link queries
  Loki for the same trace ID, over the span's time range widened by five
  minutes either side.

Retention is 30 days, matching Loki, so a trace and the logs that reference it
expire together. Completed blocks live in the `tempo` MinIO bucket. The
`tempo_data` host volume holds only the write-ahead log and blocks not yet
flushed.

Tempo's own gRPC server runs on 9096 rather than its default 9095, which Loki
already holds on that node.

For a Python service, see
[How to send Python traces to Tempo](../how-to/send-python-traces-to-tempo.md).

## `localstack monitor`, and what it is not

`localstack monitor` is a terminal panel showing four things: Vault's seal
state, node status, per-job allocation health, and failing Consul checks. It
answers "is the cluster fine and is my job running" without opening a
browser.

It is not part of this stack and does not overlap with it. No metrics, no
charts, no history, no logs, no alerting. Current control-plane state only,
read from the Nomad, Vault and Consul APIs. Everything else
stays Grafana's, Prometheus's and Loki's job.

Each source is fetched on its own with its own timeout, so a sealed Vault
degrades one panel instead of hanging the screen. A fetch that fails keeps
the last value and marks it stale. `q` quits, `r` refreshes now.

```bash
localstack monitor                # refresh every 5 seconds
localstack monitor --refresh 20   # slower
localstack monitor --refresh 0    # only when you press r
```

Run `localstack login` first. The command exits without a session, because
the Nomad reads need the token it brokers.

It reads its addresses from `VAULT_ADDR`, `NOMAD_ADDR` and
`CONSUL_HTTP_ADDR`. Point them at the edge:

```
VAULT_ADDR=https://vault.lab.orangecluster.nl
NOMAD_ADDR=https://nomad.lab.orangecluster.nl
CONSUL_HTTP_ADDR=https://consul.lab.orangecluster.nl
```

Those work from the LAN and over tailscale, and they keep working when the
plaintext ports 4646, 8200 and 8500 close to the LAN.

The seal-state and Consul reads need no token, so those two panels work for
anyone. The node and job panels need a Nomad token carrying `list-jobs` and
`node:read`.

`localstack login` brokers a second Nomad credential, `nomad/creds/manage`,
for exactly this: `nomad/creds/deploy`'s policy grants neither `list-jobs`
nor `node:read`, so the node and job panels read through `manage` instead.
A denial still names the capability it is missing rather than showing an
empty table, which is the designed behavior for a genuine policy gap.
