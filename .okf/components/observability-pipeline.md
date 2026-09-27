---
type: component
title: The observability pipeline
description: "How metrics, logs, traces and alerts move through the cluster today: which Terraform root owns each of Prometheus, Grafana, Loki, Tempo, Alloy and node-exporter, why they split across both roots, and the traps that shaped Tempo's memory, the keyless MinIO access and the alert rules."
tags: [monitoring, prometheus, grafana, loki, tempo, alloy, alerting, observability]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: prometheus-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/prometheus.hcl
  - id: grafana-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/grafana.hcl
  - id: alert-rules
    resource: git:3ec5d1e:deployments/infrastructure/services/grafana/alert-rules.yaml
    note: "The working tree differs from 3ec5d1e (uncommitted operator edits), and this concept describes the working tree."
  - id: alloy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/alloy.hcl
  - id: loki-jobspec
    resource: git:3ec5d1e:deployments/applications/services/loki.hcl
  - id: tempo-jobspec
    resource: git:3ec5d1e:deployments/applications/services/tempo.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-storage
    resource: git:3ec5d1e:deployments/applications/storage.tf
  - id: N1-netsec-restrict-prometheus-loki-to-cluster
    resource: loop:N1-netsec-restrict-prometheus-loki-to-cluster
  - id: G1-grafana-native-oidc-login
    resource: loop:G1-grafana-native-oidc-login
  - id: G3-alerts-standalone-telegram-bot
    resource: loop:G3-alerts-standalone-telegram-bot
  - id: R9-rollout-tempo-keyless-minio
    resource: loop:R9-rollout-tempo-keyless-minio
  - id: R13-rollout-loki-registry-keyless-minio
    resource: loop:R13-rollout-loki-registry-keyless-minio
---

# The observability pipeline

Six Nomad jobs collect and show what the cluster does. Four of them are in the
infrastructure root and two in the applications root. Apart from the host
volumes, no Terraform reference connects the two halves: every other link
between them is a literal node address.
What each service exposes to a user is in `docs/reference/monitoring.md`. The
original build plan, kept as history, is
[Monitoring stack original build plan](/components/monitoring-stack.md).

## The pieces

| Job | Root | Placement | Ports | Durable state |
|---|---|---|---|---|
| `node-exporter` | infrastructure | system job, every node | 9100 | none |
| `alloy` | infrastructure | system job, every node | 12345, OTLP 4319/4320 on loopback | positions in the alloc dir |
| `prometheus` | infrastructure | `ubuntu` (192.168.2.47) | 9090 | `prometheus_data` host volume, 30d TSDB |
| `grafana` | infrastructure | `ubuntu` | 3000 | `grafana_data` host volume |
| `loki` | applications | `ubuntu` | 3100, gRPC 9095 | `loki` MinIO bucket, WAL on `loki_data` |
| `tempo` | applications | `ubuntu` | 3200, gRPC 9096, OTLP 4317/4318 | `tempo` MinIO bucket, WAL on `tempo_data` |

The jobspecs are under `deployments/infrastructure/services/` and
`deployments/applications/services/`. All four host volumes are
`nomad_dynamic_host_volume` resources in
`deployments/infrastructure/services.tf`, including the two that Loki and Tempo
mount.

## Why the stack spans two roots

Loki and Tempo are in the applications root because their MinIO bucket and
their `minio_iam_policy` are there (`deployments/applications/storage.tf`).
Their host volumes are in the infrastructure root. So the apply order is
infrastructure first, then applications. Applying applications first registers
a job whose volume does not exist yet, and the alloc waits.

The rest crosses the roots by literal address. Grafana's datasources dial
`192.168.2.47:9090`, `:3100` and `:3200`. Alloy pushes to
`192.168.2.47:3100/loki/api/v1/push` and exports traces to `192.168.2.47:4317`.
Moving Loki or Tempo off `ubuntu` means editing by hand, with no plan pointing
at any of them: `grafana.hcl`, `alloy.hcl`, the `tempo` target in
`prometheus.hcl`, the traces endpoint in OpenViking's `ov.conf.json` and
`TEMPO_OTLP` in `scripts/check_openviking_config.py`, the firewall rules, and
the host volumes' node constraint.

## How each signal travels

**Metrics.** Prometheus scrapes three kinds of target
(`deployments/infrastructure/services/prometheus.hcl`):

- Static targets for Nomad (all five agents), Consul, HAProxy, the Postgres
  exporter, MinIO, Tempo and node-exporter. The `node` and `nomad` jobs
  relabel `instance` to the hostname.
- Dedicated jobs for Bifrost and OpenViking. Bifrost's `/metrics` needs basic
  auth since B1, and the shared discovery job cannot carry a per-target
  credential. The credential is a copy at `default/prometheus/bifrost-admin`,
  written by `vault_kv_secret_v2.prometheus_bifrost_admin` in
  `deployments/infrastructure/secrets.tf` from the externally seeded
  `default/bifrost/credentials`. Rotating the source without an infrastructure
  apply leaves Prometheus scraping with a stale password and reading 401.
- `consul_services`, which keeps any Consul service tagged `prometheus` and
  honors a `metrics_path` service meta key. embark and driftwatch arrive this
  way.

memex is not scraped: its `/metrics` needs auth, and `prometheus.hcl` carries
only a note saying so.

**Logs.** Alloy replaced Promtail (end of life 2 March 2026) in `9a84f24`. It
reads journald and every Nomad alloc's `*.std{out,err}.N` files, and derives
`alloc_id`, `task` and `stream` from the path with three anchored relabel
rules, because Alloy has no filename source for a regex stage. It keeps its
read positions under `/alloc/data/alloy` so a restart resumes rather than
re-ships.

**Traces.** Two roads reach Tempo. A workload that follows the cluster
convention sends OTLP to `127.0.0.1:4319` on its own node, and Alloy batches
and forwards it to Tempo (`9767488`). embark does this. OpenViking exports
straight to `192.168.2.47:4317` from its own `ov.conf.json`. Alloy's receiver
binds loopback on purpose: producers never learn where Tempo is, and no
firewall rule is needed.

Grafana links logs to traces with two derived fields on the Loki datasource:
a regex over the JSON body for tailed Nomad logs, and a structured-metadata
label for OTLP-ingested logs, which nothing ships yet. The body match needs a
service that writes JSON logs with a `trace_id` field. As of the jobspec
comment, embark writes JSON but no trace ids, so the link is armed rather
than live.

## Traps that shaped the current config

- **Alloy's OTLP ports are 4319/4320, not the defaults.** Alloy is a system
  job, so claiming a port another job already binds on some node fails
  placement on that node, and that node's logs stop shipping without an error.
  The same reasoning sets Alloy's reservation to 128 MB with `memory_max = 256`:
  the reservation has to fit the tightest node (`orangepi4a`).
- **Tempo's 768 MB is a ceiling, not headroom.** `GOMEMLIMIT = "600MiB"` is
  what stopped the OOM loop, because Go's GC knows nothing about the cgroup
  cap. On 2026-09-11 it settled at about 266 MiB replaying the WAL the
  unbounded config had died on every 18 seconds. The jobspec's order of levers
  is: lower `GOMEMLIMIT`, then `parquet_row_group_size_bytes`, and only then the
  memory figure.
- **The metrics generator runs `local-blocks` only.** It writes no series, so
  Prometheus is untouched. Its purpose is TraceQL metrics over span attributes
  such as `span.ov_retrieval.keyword_hits`. `storage.path` must be set or the
  generator disables itself with an info-level log and every query returns
  empty. `max_live_traces` is the only bound on the live-trace map, and
  exceeding it drops traces, which is what `TempoTracesDropped` watches.
  `max_live_traces_bytes` cannot take effect on this path, and the jobspec
  traces why through Tempo's source.
- **Keyless MinIO access differs per client library.** Both jobs mount a
  Workload Identity JWT at `secrets/nomad_minio.jwt` and MinIO resolves the
  policy by the `nomad_job_id` claim, so each `minio_iam_policy` name must equal
  its job id exactly. Tempo uses minio-go's web-identity provider (R9): the
  scheme on `TEST_IAM_ENDPOINT` is load-bearing, and dropping it gives silent
  anonymous S3. `AWS_ROLE_ARN` must stay unset or the exchange switches to
  role-policy mode. Loki vendors aws-sdk-go v1, which cannot target a non-AWS
  STS, so R13 gave it a `credential_process` helper at `local/minio-creds.sh`.
  `AWS_CONFIG_FILE` must be set and `AWS_WEB_IDENTITY_TOKEN_FILE` must not be.
  The static keys at `default/loki/minio` and `default/tempo/minio` stay in
  Vault as the rollback path. Neither job has a `vault {}` block.
- **Grafana's login has four settings that look optional.** Grafana 11.5.2's
  generic OAuth client does no OIDC discovery, so the three URLs are written
  out. `SCOPES` must contain `openid`. `ROLE_ATTRIBUTE_PATH` is a quoted
  literal, or every user lands as Viewer. `GF_SERVER_ROOT_URL` must match
  `local.grafana_redirect_url` in `deployments/infrastructure/oidc.tf`, and a
  mismatch fails at Vault with an opaque error (G1).

## Grafana is provisioned from the jobspec

Datasources, 13 dashboards, the contact point, the notification policy, the
message template and the alert rules are all Nomad templates. Terraform reads
each dashboard JSON and `alert-rules.yaml` with `file()` and passes it through
`templatefile`, so they are part of `nomad_job.grafana.jobspec`. Any edit to
one of those files, a comment included, re-registers Grafana. The dashboards
and rules use `<<<<` and `>>>>` as template delimiters so consul-template
leaves Grafana's own `{{ }}` alone, and the rules placeholder sits at column 0
so the YAML keeps its indentation. Dashboards load with `allowUiUpdates: false`:
an edit made in the UI does not persist.

Alerts go to one Telegram chat through OrangeClusterAlertBot, a send-only bot
separate from Hermes's (G3). Its token is hand-written at
`default/grafana/telegram`, and `var.telegram_alert_chat_id` holds the chat.
No Terraform resource writes the token, so swapping bots is a Vault edit. The
user-facing side is under "Where alerts go" in `docs/reference/monitoring.md`.

`alert-rules.yaml` holds two groups. `cluster-health` evaluates every minute.
`retrieval-quality` evaluates every five minutes and mixes 14-day trend rules
with fixed thresholds. See [driftwatch](/components/driftwatch.md).
Two rules couple the file to other jobs:

- `ScrapeJobMissing` asserts that ten named scrape jobs exist. For static
  targets such as `bifrost` and `openviking`, the series exists as soon as
  Prometheus has the job. For a Consul-discovered job such as `driftwatch`, it
  fires if the service is still unregistered 10 minutes after an
  infrastructure apply that names it.
- `OpenVikingDown` carries a 50m `for`, sized off OpenViking's measured 44m46s
  worst boot. `OpenVikingNotReady` carries 10m and sees no data during a boot.
  See [the OpenViking service](/components/openviking-service.md). In the
  working tree these two rules are new and uncommitted. The block above them
  records a known gap: this Nomad build exports no restart series, so a restart
  loop with fast boots raises no alert.

## Firewall

Prometheus, Loki and Tempo answer without authentication, so their ufw rules
name callers (N1). The Prometheus, Grafana and node-exporter rules are in
`local.firewall_rules` in `deployments/infrastructure/services.tf`. The Loki
and Tempo rules are in the same local in `deployments/applications/services.tf`.
Loki's push port and Tempo's OTLP ports admit all five node addresses, because
every node ships.
Grafana stays LAN and tailnet wide on 3000, since it authenticates.

Every rule is one-way: `null_resource.firewall` runs `ufw allow` on create and
nothing on destroy. N1 also found that any ufw write rebuilds the live chain
from `/etc/ufw/user.rules`, and a dry run showed the narrowing apply would have
dropped a hand-added Grafana rule. N1 saved it in the same apply. That is
[ufw rules outside user.rules](/practices/ufw-rules-outside-user-rules.md).
Why none of these services is behind the edge is
`docs/explanation/why-monitoring-is-not-behind-the-edge.md`.

## Invariants and what enforces them

| Must stay true | Enforced by |
|---|---|
| `minio_iam_policy` names equal the job ids `loki` and `tempo` | nothing, and a mismatch fails the STS exchange at runtime |
| Grafana root URL equals the registered redirect URI | nothing, and a mismatch fails at login |
| Every node address stays on the Loki push and Tempo OTLP rules | nothing, and a missing node's data stops silently |
| Named scrape jobs exist | `ScrapeJobMissing` |
| The Bifrost scrape credential matches Bifrost's admin login | nothing but an infrastructure apply after each rotation |

## Not built

O1 (stub) would route opted-in spans to an LLM trace backend as a second leg
out of Alloy. T5 (blocked) would alert on edge certificate expiry and needs a
blackbox exporter first.

## Related

- [The host firewall](/components/host-firewall.md)
- [Host volumes](/components/host-volumes.md)
- [MinIO](/components/minio.md)
- [The workload identity chain, as
  built](/components/workload-identity-chain.md)
- [The two Terraform roots](/components/terraform-roots.md)
