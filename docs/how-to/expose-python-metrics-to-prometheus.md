# How to expose Python metrics to Prometheus

## Introduction

Wire a Python service's metrics into Prometheus. Once the one-time scrape
config in step 3 is in place, Prometheus finds a new app through Consul with
no config change.

## Prerequisites

- A running monitoring stack, described in the
  [monitoring stack reference](../reference/monitoring.md).
- A Python service deployed as a Nomad job.

## Directions

### Step 1: Expose `/metrics` from the app

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

### Step 2: Register a metrics service in the Nomad job

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

**Why two services.** A single Consul service can only register one port. The metrics port is registered separately so Prometheus's `consul_sd_config` can resolve it directly without dereferencing meta. The `prometheus` tag is what triggers scraping — drop the tag to opt out.

### Step 3: Check the Prometheus scrape config

This is one-time, in the `services/prometheus.hcl` template:

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

### Step 4: Open the metrics port in the firewall

Open the chosen metrics port to `192.168.2.47` (Prometheus) on whichever node the app runs on. Add a rule entry alongside the per-app rules in `deployments/infrastructure/services.tf`'s `locals.firewall_rules`.

## Additional resources

- [Python service observability reference](../reference/python-observability.md)
- [Monitoring stack reference](../reference/monitoring.md)
