---
domain: devops
version: "1.0"
sources:
  - "Nomad HTTP API v1"
  - "Consul Health API v1"
---

# Cluster Knowledge Base

## Cluster Context

This is a single-server Nomad cluster (datacenter: `localstack`). There is no HA — if the server node goes down, the entire control plane is unavailable. That is always a critical finding.

All nodes run Podman as the container runtime (not Docker).

Do not assume a fixed set of nodes or jobs. Discover them dynamically via the API every run.

## Nomad API Patterns

All endpoints are relative to the Nomad address (from `nomad_addr` setting). Authenticate every request with the header `X-Nomad-Token: {NOMAD_TOKEN env var}`.

### Node inspection
- `GET /v1/nodes` — all client nodes with status
- `GET /v1/node/{id}` — full node detail (resources, attributes, drivers)
- `GET /v1/node/{id}/allocations` — all allocations on a node

### Job inspection
- `GET /v1/jobs` — list all jobs
- `GET /v1/job/{id}` — full job spec
- `GET /v1/job/{id}/summary` — per-task-group running/desired/failed counts
- `GET /v1/job/{id}/allocations` — all allocations for a job

### Allocation inspection
- `GET /v1/allocations` — all allocations (can be large; filter client-side)
- `GET /v1/allocation/{id}` — full allocation detail with task states and events

### Evaluations
- `GET /v1/evaluations` — recent evaluations
- Blocked evals indicate scheduling failures (resource exhaustion, constraint mismatches)

## Memex Conventions

### KV Namespace

All KV keys MUST use the prefix `app:openfang:cluster-watchdog:`. This scopes your state to avoid collisions with other agents/hands.

| Key | Purpose |
|-----|---------|
| `app:openfang:cluster-watchdog:last_run` | ISO 8601 timestamp of last completed run |
| `app:openfang:cluster-watchdog:issue:{name}` | Tracked open issue (value: description + first-seen date, or "resolved — {date}") |

### Notes

- Tag all notes with `cluster-watchdog` so they are discoverable.
- Use additional tags to categorize: `daily-report`, `triage`, `critical`, `warning`, `incident`.
- Use YAML frontmatter (title, description, tags) — required for Memex indexing.

## Common Failure Modes

| Symptom | Likely Cause | Triage Action |
|---------|-------------|---------------|
| Node status `down` | Network issue or node crashed | SSH to node, check `systemctl status nomad` |
| Node `ineligible` | Manual drain or maintenance | Check if intentional via `nomad node status` |
| Allocation `failed` with exit code 137 | OOM killed | Increase memory in job spec or check for memory leak |
| Allocation `failed` with exit code 1 | Application crash | Check application logs via `nomad alloc logs` |
| Allocation `pending` | Resource exhaustion or constraint mismatch | Run `nomad node status -stats` on target node |
| Driver failure `podman` | Podman daemon issue | Restart podman on the node: `systemctl restart podman` |
| Blocked evaluation | No node satisfies constraints | Review job constraints vs available nodes |
| Repeated restarts | Crash loop | Check restart policy and underlying cause |

## Telegram Formatting

- Max message length: 4096 characters. Split into multiple messages if needed.
- Use monospace for node/job names and commands: backtick-wrap them.
- Keep severity prefixes consistent: `[CRITICAL]`, `[WARNING]`, `[INFO]`.
- Lead with the worst findings — if everything is healthy, a short "all clear" is fine.
