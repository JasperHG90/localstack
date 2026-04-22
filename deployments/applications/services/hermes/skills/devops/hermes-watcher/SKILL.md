---
name: hermes-watcher
description: Monitors Hermes gateway logs for errors and failures, writes structured post-mortems to Memex for later triage
version: 1.0.0
metadata:
  hermes:
    tags: [devops, monitoring, self-healing, hermes]
    category: devops
---
## When to Use

Scheduled every 30 minutes to scan gateway logs for errors. Also invoke manually when investigating Hermes operational issues.

## Procedure

### Phase 1: Collect Recent Logs

Use the terminal to read the Hermes log files:

```
cat /opt/data/logs/*.log | tail -500
```

Also check stderr output if available. Focus on the last 30 minutes of log entries.

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
2. Check Memex KV for prior occurrence: GET /kv/get?key=app:hermes:hermes-watcher:issue:{slug}
3. If seen in the last 6 hours, skip (already reported)
4. If new or recurred after resolution, proceed to Phase 4

### Phase 4: Write Post-Mortem

For each new issue, write a structured note to Memex:
- vault: inbox (sorting-hat will route it)
- author: hermes-watcher
- tags: hermes-watcher, post-mortem, {severity}, {category}
- note_key: hermes-watcher:issue:{slug}
- Content: what happened, log excerpt, probable cause, suggested fix

Also update KV tracker: PUT /kv with key app:hermes:hermes-watcher:issue:{slug} and value containing timestamp + description. Set ttl_seconds to 21600 (6 hours).

### Phase 5: Summary

If any HIGH or CRITICAL issues were found, produce a brief summary. Otherwise respond with [SILENT].

Update KV: app:hermes:hermes-watcher:last_run with current timestamp.

## Pitfalls

- Do not report every WARNING — only patterns that indicate real problems
- Deduplicate against recent KV entries to avoid flooding Memex
- Provider rate limits (402) are informational, not critical
- Untitled sessions are a known cosmetic issue, do not report
