---
description: "Get a Python service's logs into Loki as JSON by writing them to stdout for Alloy to ship."
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/alloy.hcl
---

# How to ship Python logs to Loki

## Introduction

Get a Python service's logs into Loki as JSON you can query in Grafana.
Alloy runs as a `system` job on every node and tails Nomad's per-task log
files under `/opt/nomad/data/alloc/*/alloc/logs/`, so anything your app
writes to stdout or stderr ends up in Loki with no HTTP push and no extra
dependency.

## Prerequisites

- A running monitoring stack, described in the
  [monitoring stack reference](../reference/monitoring.md).
- A Python service deployed as a Nomad job.

## Directions

### Step 1: Install a JSON log formatter

```bash
uv add python-json-logger
```

### Step 2: Log JSON to stdout

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

Alloy ships the line as-is with the labels `job="nomad"`, `host` (the
node), `alloc_id`, `task` and `stream` (`stdout` or `stderr`). LogQL parses
the JSON at query time, so `{job="nomad"} |= "error" | json | level="ERROR"`
works with no shipper-side config.

**Don't log to files.** Logging to a file inside the container loses the
logs when the alloc restarts and bypasses Alloy entirely. Log to stdout
only.

**Direct Loki push (avoid).** `python-logging-loki` lets the app push
directly to `http://192.168.2.47:3100/loki/api/v1/push`. Skip it: it adds a
network failure mode, complicates secrets, and loses the labels Alloy
attaches automatically.

## Additional resources

- [Python service observability reference](../reference/python-observability.md)
- [How to send Python traces to Tempo](send-python-traces-to-tempo.md)
