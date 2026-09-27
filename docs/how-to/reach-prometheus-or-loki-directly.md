# How to reach Prometheus or Loki directly

## Introduction

Grafana covers the day-to-day. Three things it does not give you:

- **Status > Targets**, which shows the real scrape failure text
  (`connection refused`, `context deadline exceeded`, a TLS error). Grafana
  can tell you `up == 0` but not why.
- The **expression browser** with metric-name autocomplete, for working out a
  query before putting it on a dashboard.
- Loki's **HTTP API**, for scripted queries or checking `/ready` when the
  ingester looks unhappy.

This works from anywhere you can SSH to the node, LAN or tailnet, and needs
no firewall change: the connection to Prometheus originates on
`192.168.2.47` itself, which is already on its own allow-list.

## Prerequisites

- SSH access to `raspberry@192.168.2.47`, from the LAN or the tailnet.

## Directions

### Step 1: Open an SSH tunnel

Forward both ports over SSH. The tunnel exists only while the command runs,
so nothing is left open afterwards:

```bash
ssh -L 9090:192.168.2.47:9090 -L 3100:192.168.2.47:3100 raspberry@192.168.2.47
```

If port 9090 or 3100 is already taken locally, pick any free local port: the
left-hand number is yours, the right-hand pair is the target. `-L
19090:192.168.2.47:9090` then serves on `http://localhost:19090`.

### Step 2: Query Prometheus or Loki

Then, in another shell or a browser:

```bash
open http://localhost:9090/targets              # scrape health, with error text
open http://localhost:9090/query                # expression browser (/graph redirects here)
curl -s http://localhost:3100/ready             # Loki readiness
curl -s --get http://localhost:3100/loki/api/v1/labels   # Loki label list
```

### Step 3: Close the tunnel

Close it with `Ctrl-C`, or `exit` if you took a shell with it. To run it in
the background instead, add `-f -N` and kill it by port when you are done:

```bash
ssh -f -N -L 9090:192.168.2.47:9090 raspberry@192.168.2.47
pkill -f '9090:192.168.2.47'
```

## Additional resources

- [Monitoring stack reference](../reference/monitoring.md)
- [Why monitoring is not behind the edge](../explanation/why-monitoring-is-not-behind-the-edge.md)
