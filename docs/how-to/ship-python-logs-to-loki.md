# How to ship Python logs to Loki

## Introduction

Alloy runs as a `system` job on every node and tails `/opt/nomad/data/alloc/*/alloc/logs/*` — Nomad's per-task log files. Anything your app writes to stdout/stderr ends up in Loki. No HTTP push, no extra dependency.

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

Alloy ships the line as-is and labels it with the job, task, alloc and node it came from. LogQL parses the JSON at query time, so `{job="nomad"} |= "error" | json | level="ERROR"` works with no shipper-side config.

**Don't log to files.** Logging to a file inside the container loses the logs when the alloc restarts and bypasses Alloy entirely. Stdout only.

**Direct Loki push (avoid).** `python-logging-loki` lets the app push directly to `http://192.168.2.47:3100/loki/api/v1/push`. Skip it: it adds a network failure mode, complicates secrets, and costs you the alloc/job/node labels Alloy attaches automatically.

## Additional resources

- [Python service observability reference](../reference/python-observability.md)
- [How to send Python traces to Tempo](send-python-traces-to-tempo.md)
