---
description: How a Python service on the cluster reaches Prometheus, Loki, Tempo and Grafana, and the naming conventions that make the links work.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/prometheus.hcl
  - resource: deployments/infrastructure/services/alloy.hcl
  - resource: deployments/infrastructure/services/grafana.hcl
---

# Python service observability

How a Python service deployed on this cluster is wired into Prometheus, Loki,
Tempo, and Grafana. Assumes the monitoring stack from
[Monitoring stack](monitoring.md) is up.

## Summary

1. Expose `/metrics` on a dedicated port using `prometheus_client`.
2. Register the metrics port as a Nomad service in Consul with the tag
   `prometheus`. Prometheus finds it through Consul service discovery and
   scrapes that service's address and port.
3. Log structured JSON to stdout. Alloy tails Nomad alloc logs, with no per-app
   config.
4. Send traces over OTLP: two environment variables, pointing at Tempo or at the
   node's Alloy on `127.0.0.1:4319` (see [Sending
   traces](monitoring.md#sending-traces)).
5. View in Grafana: pre-provisioned Prometheus, Loki and Tempo datasources are already there.

The steps for each are in
[How to expose Python metrics to Prometheus](../how-to/expose-python-metrics-to-prometheus.md),
[How to ship Python logs to Loki](../how-to/ship-python-logs-to-loki.md) and
[How to send Python traces to Tempo](../how-to/send-python-traces-to-tempo.md).

## Grafana

### Querying

- **Metrics:** `Explore`, then the Prometheus datasource. The `job` label equals
  the Consul service name (`myapp-metrics`), `instance` is the Consul node name.
  Example: `rate(myapp_requests_total{status="500"}[5m])`.
- **Logs:** `Explore`, then the Loki datasource. Filter by Nomad task:
  `{task="myapp"} | json | level="ERROR"`.
- **Traces:** `Explore`, then the Tempo datasource. Search by service name, or
  paste a trace ID.
- **Correlation:** the Loki datasource ships with a derived field on `trace_id`,
  so that field in a log line is already a link into Tempo. It is provisioned in
  `deployments/infrastructure/services/grafana.hcl`, not configured in the UI.

### Dashboards

For a new app, start with the Grafana "New dashboard from query" flow against the Prometheus datasource. For RED-method dashboards (Rate / Errors / Duration), import community dashboard 14282 and override the `job` variable to match.

## Conventions

- Metric port: pick a free static port per app (registry: keep a list on this page if it grows).
- Metrics endpoint always at `/metrics`. Leave the path default. Override it
  only with the `metrics_path` Consul meta if forced.
- Log levels: `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`, uppercase, standard
  Python.
- Trace IDs: if you propagate them, log them under the field name `trace_id` so Grafana derived fields work without per-app config.

## See also

- [Monitoring stack](monitoring.md): who can reach each service, and where
  alerts go.
- Prometheus Consul SD: <https://prometheus.io/docs/prometheus/latest/configuration/configuration/#consul_sd_config>
- Alloy `loki.source.file`: <https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/>
