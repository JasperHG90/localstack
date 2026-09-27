# How to send Python traces to Tempo

## Introduction

Tempo accepts OTLP directly, so there is no agent to configure and no per-app
Nomad wiring.

## Prerequisites

- A running monitoring stack, described in the
  [monitoring stack reference](../reference/monitoring.md).
- A Python service deployed as a Nomad job.

## Directions

### Step 1: Install the SDK

```bash
uv add opentelemetry-distro opentelemetry-exporter-otlp
```

### Step 2: Set two environment variables

Set two environment variables in the job's `env` block:

```hcl
env {
  OTEL_EXPORTER_OTLP_ENDPOINT = "http://192.168.2.47:4317"
  OTEL_SERVICE_NAME           = "myapp"
}
```

`OTEL_SERVICE_NAME` becomes the service name Tempo indexes and the one you
search on in Grafana, so set it per app rather than letting it default.

### Step 3: Run the app under auto-instrumentation

Auto-instrumentation covers most libraries without code changes:

```bash
opentelemetry-instrument python -m myapp
```

### Step 4: Log the trace ID

To link a trace back to its logs, log the trace ID under `trace_id` (see
[Conventions](../reference/python-observability.md#conventions)). Grafana turns
that field into a link into Tempo, and the Tempo datasource links the other
way.

## Additional resources

- [Python service observability reference](../reference/python-observability.md)
- [Monitoring stack reference](../reference/monitoring.md#sending-traces)
