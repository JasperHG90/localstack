---
name: post-mortem
description: Receives issue reports, deduplicates them, and maintains structured post-mortem notes in the Memex inbox vault
version: 1.1.0
metadata:
  hermes:
    tags: [devops, incident, post-mortem, memex]
    category: devops
---

## When to Use

Activate when another skill or agent reports an error, failure, or operational issue that needs to be recorded. This skill is the single entry point for persisting structured incident records.

## Configuration

- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl.

## Procedure

### Forbidden Actions

Do NOT use the memory search endpoint (`memex_recall` / `memex_memory_search`) for deduplication. Use note search with specific tags (`memex_retrieve_notes` / `memex_find_note`) instead.

### Step 1: Verify the Vault

On first invocation, confirm the `inbox` vault exists:

```
memex_get_vault_summary(vault_id="inbox")
```

If the call fails because the vault does not exist, stop and report an error -- you cannot persist without it.

### Step 2: Generate a Deterministic Issue Slug

Create a lowercase, hyphen-separated, short identifier for the issue (e.g. `postgres-oom-killed`, `nomad-api-unreachable`, `note-migration-failed`, `github-rate-limited`). The slug MUST be stable -- the same underlying problem must always produce the same slug so deduplication works.

### Step 3: Check for Prior Occurrences

Check the KV store for an existing tracker entry:

```
memex_kv_get(key="app:hermes:post-mortem:processed:{issue-slug}")
```

- **If found:** this is a recurrence. Parse the JSON value to get `first_seen`, `occurrence_count`, and `reporters`. Increment `occurrence_count`, update `last_seen`, merge the new reporter into the list.
- **If not found:** this is a new issue. Set `occurrence_count = 1`, `first_seen = now`, `reporters = [reporting skill]`.

### Step 4: Create or Update the Post-Mortem Note

Use the native Memex plugin tool to create/upsert the note:

```
memex_retain(
  title="Post-Mortem: {issue-slug}",
  author="post-mortem",
  description="One-sentence summary of the issue",
  tags=["post-mortem", "hermes", ...reporter tags, ...domain tags],
  markdown_content=<raw markdown body, see below>,
  vault_id="inbox",
  note_key="post-mortem:{issue-slug}",
  background=True
)
```

`markdown_content` takes the raw markdown body — no base64 encoding.

The note content (do NOT include YAML frontmatter -- it is auto-generated):

```markdown
## Summary

{What happened -- based on the reporting skill's description}

## Cause

{Root cause if the reporter identified one, otherwise "Under investigation"}

## Likely Fix

{What would most likely resolve this, based on the reporter's suggestion}

## Metadata

- **Issue ID:** {issue-slug}
- **First seen:** {ISO timestamp}
- **Last seen:** {ISO timestamp}
- **Occurrences:** {count}
- **Reported by:** {comma-separated list of skill IDs}
- **Status:** {Active if count == 1, Recurring if count > 1}
```

### Step 5: Update the Tracker

Write the updated tracker entry to KV:

```
memex_kv_write(
  key="app:hermes:post-mortem:processed:{issue-slug}",
  value="{\"first_seen\": \"...\", \"last_seen\": \"...\", \"occurrence_count\": N, \"reporters\": [\"skill-a\", \"skill-b\"]}"
)
```

### Step 6: Acknowledge

Reply to the reporting skill confirming the post-mortem was created or updated, and whether this is a new issue or a recurrence.

### Domain Tag Mapping

When creating post-mortem notes, add domain-specific tags based on which skill reported the issue:

| Reporting Skill | Additional Tags |
|----------------|-----------------|
| `cluster-watchdog` | `cluster`, `infrastructure` |
| `trader-advisor`, `trend-scout`, `market-analyst` | `trading`, `finance` |
| `blog-scraper`, `medium-reader` | `engineering`, `agentic` |
| `sorting-hat`, `insight-linker`, or any other skill | `system` |

For example, if `cluster-watchdog` reports an issue, the tags array would be: `["post-mortem", "hermes", "cluster-watchdog", "cluster", "infrastructure"]`.

### Error Handling

- If the vault summary call fails or `inbox` is missing: reply with an error. Do not attempt to save.
- If `memex_retain` fails: reply with the error so the reporting skill knows the report was not persisted.
- If KV writes fail: log warning, continue. State self-corrects on next report.

## Pitfalls

- The issue slug must be deterministic -- the same underlying problem must always produce the same slug, or deduplication breaks.
- Always pass `note_key` when calling `memex_retain` to enable upsert behavior. Without it, duplicate notes will be created.
- KV namespace is `app:hermes:post-mortem:` -- do not use the old `app:openfang:post-mortem:` prefix.
