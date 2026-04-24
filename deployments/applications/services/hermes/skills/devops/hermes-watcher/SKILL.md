---
name: hermes-watcher
description: Monitors Hermes gateway logs for errors and failures, writes structured post-mortems to Memex for later triage
version: 1.1.0
metadata:
  hermes:
    tags: [devops, monitoring, self-healing, hermes]
    category: devops
---
## When to Use

Scheduled every 30 minutes to scan gateway logs for errors. Also invoke manually when investigating Hermes operational issues.

## Configuration

- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl.

## Procedure

### Phase 1: Collect Recent Logs

**CRITICAL**: Only consider log entries from the **last 35 minutes**. Older errors are stale — they were either already reported in a prior watcher run, or fixed before this run started. Reporting them again creates noise.

Compute the cutoff:
```
CUTOFF=$(date -u -d '35 minutes ago' '+%Y-%m-%d %H:%M:%S')
```

Then filter logs by timestamp. Hermes log lines start with `YYYY-MM-DD HH:MM:SS,nnn`:
```
awk -v c="$CUTOFF" '$1" "$2 >= c' /opt/data/logs/errors.log
awk -v c="$CUTOFF" '$1" "$2 >= c' /opt/data/logs/agent.log | tail -200
```

If both filters return empty, respond with `[SILENT]` and exit. Nothing new to report.

### Phase 2: Classify Issues

Scan logs for these patterns:

| Pattern | Severity | Category |
|---------|----------|----------|
| `ERROR` or `Traceback` | HIGH | runtime-error |
| `failed to connect` or `Connection refused` | HIGH | connectivity |
| `InvalidToken` or `Unauthorized` or `401` | HIGH | auth |
| `402` or `credits` or `rate limit` | MEDIUM | provider-limit |
| `404.*endpoints` or `unknown provider` | MEDIUM | config |
| `Refusing to start` or `Refusing to bind` | HIGH | startup |
| `WARNING` | LOW | warning |
| `skill.*not found` | MEDIUM | skill-config |
| `OOM` or `Killed` or exit code `137` | CRITICAL | resource |

### Phase 3: Deduplicate

For each issue found:
1. Generate a slug from the error type and message
2. Check Memex KV for prior occurrence:
   ```
   memex_kv_get(key="app:hermes:hermes-watcher:issue:{slug}")
   ```
3. If seen in the last 6 hours, skip (already reported)
4. If new or recurred after resolution, proceed to Phase 4

### Phase 4: Write Post-Mortem

For each new issue, write a structured note to Memex via the native plugin tool:

```
memex_retain(
  title="<short issue title>",
  author="hermes-watcher",
  description="<one-sentence summary>",
  tags=["hermes-watcher", "post-mortem", "<severity>", "<category>"],
  markdown_content=<raw markdown: what happened, log excerpt, probable cause, suggested fix>,
  vault_id="inbox",
  note_key="hermes-watcher:issue:{slug}",
  background=True
)
```

`markdown_content` takes the raw markdown body — no base64 encoding. `sorting-hat` will route the note from `inbox`.

Also update the KV tracker with a 6-hour TTL so the same issue is deduplicated for that window:

```
memex_kv_write(
  key="app:hermes:hermes-watcher:issue:{slug}",
  value="<ISO timestamp + short description>",
  ttl_seconds=21600
)
```

### Phase 5: Summary

If any HIGH or CRITICAL issues were found, produce a brief summary. Otherwise respond with [SILENT].

Update the last-run timestamp:
```
memex_kv_write(key="app:hermes:hermes-watcher:last_run", value="<ISO timestamp now>")
```

## Pitfalls

- Do not report every WARNING — only patterns that indicate real problems
- Deduplicate against recent KV entries to avoid flooding Memex
- Provider rate limits (402) are informational, not critical
- Untitled sessions are a known cosmetic issue, do not report
