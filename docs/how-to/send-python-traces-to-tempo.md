---
description: "Send a Python service's OpenTelemetry traces to Tempo through the node-local Alloy receiver."
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/alloy.hcl
  - resource: deployments/applications/services/tempo.hcl
---

# How to send Python traces to Tempo

## Introduction

Send a Python service's OpenTelemetry traces to Tempo, so you can search
them in Grafana. Alloy runs on every node with an OTLP receiver on
loopback and forwards what it gets to Tempo, so the app needs only the SDK
and two environment variables, and no per-app Nomad wiring.

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
  OTEL_EXPORTER_OTLP_ENDPOINT = "http://127.0.0.1:4319"
  OTEL_SERVICE_NAME           = "myapp"
}
```

Port 4319 is Alloy's gRPC receiver (4320 is HTTP), not the OTLP default
4317, because Tempo already holds 4317 on its own node. The receiver binds
`127.0.0.1` on the host, so the task must share the host's network to reach
it: the podman driver's `network_mode = "host"`, as embark uses. A task on
bridge networking cannot, and exports straight to Tempo at
`http://192.168.2.47:4317` instead.

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
