---
name: cluster-watchdog
description: Monitors the Nomad cluster, triages issues, sends daily health reports via Telegram
version: 1.0.0
metadata:
  hermes:
    tags: [devops, monitoring, nomad, consul, cluster]
    category: devops
---
## When to Use

When asked to check cluster health, when running scheduled watchdog reports, or when investigating Nomad/Consul issues.

## Configuration

- Nomad API: `$NOMAD_ADDR` (default `http://192.168.2.30:4646`)
- Consul API: `$CONSUL_ADDR` (default `http://192.168.2.30:8500`)
- Nomad token: `$NOMAD_TOKEN` (in env)
- Report style: `detailed` (full breakdown) or `short` (critical/warning only)
- Failure lookback: 24 hours
- Resource usage: enabled
- Memex API: `$MEMEX_SERVER_URL/api/v1`, auth `-H "X-API-Key: $MEMEX_API_KEY"`

## Procedure

### Phase 0: Load State

1. Check last-run timestamp via Memex KV:
   ```
   curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:cluster-watchdog:last_run"
   ```
   If found, use it to scope "recent" failures. If 404 (first run), use 24h lookback.

2. List tracked issues:
   ```
   curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv?key_prefix=app:hermes:cluster-watchdog:issue:"
   ```

3. Search past reports in Memex:
   ```
   curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
     "$MEMEX_SERVER_URL/api/v1/notes/search" \
     -d '{"query":"cluster health report","tags":["cluster-watchdog","daily-report"],"limit":5}'
   ```

### Phase 1: Node Discovery

1. Fetch all nodes: `curl -s -H "X-Nomad-Token: $NOMAD_TOKEN" "$NOMAD_ADDR/v1/nodes"`
2. For each node, fetch detail: `curl -s -H "X-Nomad-Token: $NOMAD_TOKEN" "$NOMAD_ADDR/v1/node/{node_id}"`
3. Record: name, status (ready/down/initializing), eligibility (eligible/ineligible), drain state
4. Fetch node allocations for resource usage: `GET /v1/node/{node_id}/allocations`
5. Flag any node not `ready` or not `eligible` as critical

### Phase 2: Job Health

1. Fetch all jobs: `GET /v1/jobs`
2. For each service/system job, fetch summary: `GET /v1/job/{job_id}/summary`
3. Compare Running vs Desired:
   - Running < Desired → **degraded**
   - Running == 0 && Desired > 0 → **down**
   - Failed/Lost > 0 → **unstable**
4. For degraded/down jobs, fetch allocations: `GET /v1/job/{job_id}/allocations`
5. Extract failure reasons from TaskStates → Events

### Phase 3: Recent Failures

1. Fetch recent evaluations: `GET /v1/evaluations?prefix=` (limit 50)
2. Filter blocked evaluations (resource exhaustion, constraint failures)
3. Filter failed allocations from last 24h
4. Group by job name, count occurrences

### Phase 4: Consul Service Health

1. `curl -s "$CONSUL_ADDR/v1/health/state/critical"`
2. Cross-reference with Nomad jobs
3. Append as context (don't duplicate Phase 2 findings)

### Phase 5: Triage

| Severity | Criteria |
|----------|----------|
| CRITICAL | Node down, job completely down (0 running), >3 consecutive failures |
| WARNING | Job degraded, node ineligible/draining, blocked evaluations |
| INFO | Isolated failure, high resource usage (>85% CPU/memory) |

### Phase 6: Persist State & Findings

**Always**: Update run state in Memex KV (note: KV write uses PUT):
```
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key":"app:hermes:cluster-watchdog:last_run","value":"<ISO timestamp>"}'
```
Also update: `status`, `nodes_healthy`, `nodes_total`, `jobs_running`, `jobs_total`.

**Only if CRITICAL/WARNING**: Save findings to Memex notes (content must be base64-encoded):
```
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/ingestions?background=true" \
  -d '{"name":"[SEVERITY] description — date","author":"hermes-watchdog","description":"...","tags":["cluster-watchdog","triage","severity"],"content":"<base64-encoded markdown>","vault_id":"inbox"}'
```
Encode content: `echo -n "markdown text" | base64`

Track issues in KV: `app:hermes:cluster-watchdog:issue:{name}` → description + date.

### Phase 7: Report via Telegram

Format for Telegram (detailed style):
```
Cluster Health Report — {date}

NODES ({healthy}/{total} healthy)
  {status_icon} {name} — {status} | CPU {cpu}% | Mem {mem}%

JOBS ({running}/{total} running)
  {icon} {job} — {running}/{desired} running
    Last failure: {reason}

RECENT FAILURES (last 24h)
  {job}: {count} failed allocs

TRIAGE
  [{severity}] {description}
  -> {suggested action}
```

Status icons: `+` healthy, `!` warning, `X` critical.

Send via Telegram. Max 4096 chars per message — split if needed.

### Phase 8: Escalate

For CRITICAL/WARNING findings, delegate to a subagent with the `/post-mortem` skill:
- What happened
- Root cause if identified
- Suggested fix
- Affected job/node/service

Do NOT escalate INFO-level or clean runs.

## Cluster Context

Single-server Nomad cluster (datacenter: `localstack`). No HA — server node down = entire control plane unavailable (always critical). All nodes run Podman (not Docker).

## Common Failure Modes

| Symptom | Cause | Action |
|---------|-------|--------|
| Node `down` | Network/crash | SSH, check `systemctl status nomad` |
| Node `ineligible` | Manual drain | Check if intentional |
| Exit code 137 | OOM killed | Increase memory in job spec |
| Exit code 1 | App crash | Check `nomad alloc logs` |
| Allocation `pending` | Resource exhaustion | `nomad node status -stats` |
| Blocked eval | Constraint mismatch | Review job constraints |

## Pitfalls

- All Nomad API requests need `X-Nomad-Token: $NOMAD_TOKEN` header
- Consul health endpoint does not need auth
- Do not save "all clear" reports as Memex notes — only CRITICAL/WARNING
- Split Telegram messages at 4096 chars
