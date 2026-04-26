# Instrumenting Python apps for the observability stack

How to wire a Python service deployed on this cluster into Prometheus, Loki, and Grafana. Assumes the monitoring stack from `docs/monitoring.md` is up.

## TL;DR

1. Expose `/metrics` on a dedicated port using `prometheus_client`.
2. Register the Nomad service in Consul with the tag `prometheus` and a `metrics_port` meta — Prometheus picks it up automatically via Consul SD.
3. Log structured JSON to stdout. Promtail tails Nomad alloc logs; no per-app config.
4. View in Grafana: pre-provisioned Prometheus and Loki datasources are already there.

---

## 1. Metrics

### App side

Use the official client library:

```bash
uv add prometheus-client
```

```python
from prometheus_client import Counter, Histogram, start_http_server

REQUESTS = Counter("myapp_requests_total", "Requests handled", ["endpoint", "status"])
LATENCY = Histogram("myapp_request_seconds", "Request latency", ["endpoint"])

def main():
    start_http_server(9000, addr="0.0.0.0")  # /metrics on :9000
    # ... your app
```

For FastAPI, use `prometheus-fastapi-instrumentator`. For sync frameworks, `prometheus-client` exposes a WSGI app you can mount.

**Naming:** prefix metrics with the app name (`myapp_*`). Use `_total` suffix on counters, `_seconds` on time histograms — Grafana queries assume these conventions.

### Nomad job side

Add a dedicated `metrics` port to the network block and a Consul service with the `prometheus` tag and a `metrics_port` meta:

```hcl
network {
  port "http"    { static = 8080 }
  port "metrics" { static = 9000 }
}

service {
  name = "myapp"
  port = "http"
  tags = ["app"]
  check { type = "http"; path = "/health"; interval = "10s"; timeout = "2s" }
}

service {
  name = "myapp-metrics"
  port = "metrics"
  tags = ["prometheus"]
  meta {
    metrics_path = "/metrics"
  }
  check { type = "http"; path = "/metrics"; interval = "30s"; timeout = "3s" }
}
```

### Why two services

A single Consul service can only register one port. The metrics port is registered separately so Prometheus's `consul_sd_config` can resolve it directly without dereferencing meta. The `prometheus` tag is what triggers scraping — drop the tag to opt out.

### Prometheus scrape config (one-time, in `services/prometheus.hcl` template)

```yaml
scrape_configs:
  - job_name: consul_services
    consul_sd_configs:
      - server: '192.168.2.30:8500'
    relabel_configs:
      - source_labels: [__meta_consul_tags]
        regex: '.*,prometheus,.*'
        action: keep
      - source_labels: [__meta_consul_service]
        target_label: job
      - source_labels: [__meta_consul_node]
        target_label: instance
      - source_labels: [__meta_consul_service_metadata_metrics_path]
        regex: '(.+)'
        target_label: __metrics_path__
```

After this is in place, **no Prometheus config changes are needed when adding a new app** — just register it in Consul with the `prometheus` tag.

### Firewall

Open the chosen metrics port to `192.168.2.47` (Prometheus) on whichever node the app runs on. Add a rule entry alongside the per-app rules in `deployments/infrastructure/services.tf`'s `locals.firewall_rules`.

---

## 2. Logs

### Just log JSON to stdout

Promtail runs as a `system` job on every node and tails `/opt/nomad/data/alloc/*/alloc/logs/*` — Nomad's per-task log files. Anything your app writes to stdout/stderr ends up in Loki. No HTTP push, no extra dependency.

```bash
uv add python-json-logger
```

```python
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s",
    rename_fields={"levelname": "level", "asctime": "timestamp"},
))
logging.basicConfig(level=logging.INFO, handlers=[handler])

log = logging.getLogger("myapp")
log.info("started", extra={"port": 8080, "version": "1.2.3"})
```

This produces:
```json
{"timestamp": "...", "level": "INFO", "name": "myapp", "message": "started", "port": 8080, "version": "1.2.3"}
```

Promtail's pipeline parses JSON automatically — every top-level key becomes a Loki label or extracted field, so you can query `{job_name="myapp"} |= "error" | json | level="ERROR"`.

### Don't log to files

Logging to a file inside the container loses the logs when the alloc restarts and bypasses Promtail entirely. Stdout only.

### Direct Loki push (avoid)

`python-logging-loki` lets the app push directly to `http://192.168.2.47:3100/loki/api/v1/push`. Skip it: it adds a network failure mode, complicates secrets, and costs you the alloc/job/node labels Promtail attaches automatically.

---

## 3. Grafana

### Querying

- **Metrics:** `Explore` → Prometheus datasource. The `job` label equals the Consul service name (`myapp-metrics`), `instance` is the Consul node name. Example: `rate(myapp_requests_total{status="500"}[5m])`.
- **Logs:** `Explore` → Loki datasource. Filter by Nomad task: `{nomad_task="myapp"} | json | level="ERROR"`.
- **Correlation:** with `derived fields` configured on the Loki datasource, a `trace_id` field in logs becomes a clickable link. Configure once in Grafana UI.

### Dashboards

For a new app, start with the Grafana "New dashboard from query" flow against the Prometheus datasource. For RED-method dashboards (Rate / Errors / Duration), import community dashboard 14282 and override the `job` variable to match.

---

## 4. Conventions

- Metric port: pick a free static port per app (registry: keep a list in `docs/notes/` if it grows).
- Metrics endpoint always at `/metrics` — leave the path default. Override only via the `metrics_path` Consul meta if forced.
- Log levels: `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` — uppercase, standard Python.
- Trace IDs: if you propagate them, log them under the field name `trace_id` so Grafana derived fields work without per-app config.

## See also

- `docs/monitoring.md` — stack deployment.
- Prometheus Consul SD: <https://prometheus.io/docs/prometheus/latest/configuration/configuration/#consul_sd_config>
- Promtail JSON pipeline: <https://grafana.com/docs/loki/latest/send-data/promtail/stages/json/>
