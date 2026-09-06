---
name: post-mortem
description: Receives issue reports, deduplicates them, and maintains structured post-mortems in OpenViking
version: 1.1.0
metadata:
  hermes:
    tags: [devops, incident, post-mortem, openviking]
    category: devops
---

## When to Use

Activate when another skill or agent reports an error, failure, or operational issue that needs to be recorded. This skill is the single entry point for persisting structured incident records.

## Configuration

- Use the native OpenViking tools (`viking_*`). Do not shell out to curl.
- Recurrence tracking needs EXACT-KEY reads, which OpenViking cannot do -- it
  is a semantic store, not a key-value one. Keep the tracker in
  `$HERMES_HOME/state/post-mortem.json` via the `files` toolset, and keep the
  written-up post-mortem itself in OpenViking.

## Procedure

### Forbidden Actions

Do NOT use `viking_search` for deduplication. Semantic search returns things
that are merely similar, so it will both miss recurrences and merge distinct
issues. Deduplication is the state file's job, keyed on the slug.

### Step 1: Load the Tracker

```
read $HERMES_HOME/state/post-mortem.json   (absent on first run: treat as {})
```

### Step 2: Generate a Deterministic Issue Slug

Create a lowercase, hyphen-separated, short identifier for the issue (e.g. `postgres-oom-killed`, `nomad-api-unreachable`, `note-migration-failed`, `github-rate-limited`). The slug MUST be stable -- the same underlying problem must always produce the same slug so deduplication works.

### Step 3: Check for Prior Occurrences

Look up `{issue-slug}` in the tracker you just read:

```
tracker["processed"]["{issue-slug}"]
```

- **If found:** this is a recurrence. Parse the JSON value to get `first_seen`, `occurrence_count`, and `reporters`. Increment `occurrence_count`, update `last_seen`, merge the new reporter into the list.
- **If not found:** this is a new issue. Set `occurrence_count = 1`, `first_seen = now`, `reporters = [reporting skill]`.

### Step 4: Create or Update the Post-Mortem Note

Store it in OpenViking:

```
viking_remember(
  content=<the full markdown body below, with a first line of
           "Post-Mortem: {issue-slug} -- <one-sentence summary>">,
  category="case"
)
```

`category="case"` is the right one: a post-mortem is a worked-through problem.
There is no upsert and no note key -- a recurrence writes a fresh memory whose
content states the new occurrence count, and the tracker file is what keeps
the count straight.

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

Write the updated tracker back:

```
$HERMES_HOME/state/post-mortem.json
  processed:
    "{issue-slug}": {first_seen, last_seen, occurrence_count, reporters[]}
```

Write the whole file back, do not append -- a partial write loses every other
slug's entry.

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

- If `viking_remember` fails: reply with the error so the reporting skill knows the report was not persisted.
- If the state write fails: log a warning and continue. The count is wrong until the next report, which is better than losing the post-mortem.

## Pitfalls

- The issue slug must be deterministic -- the same underlying problem must always produce the same slug, or deduplication breaks.
- `viking_remember` has no upsert. Deduplication lives entirely in the tracker
  file; if you skip reading it you will file the same issue repeatedly.
- Read-modify-write the whole state file. Two skills writing it concurrently
  is a lost update, so keep post-mortem's own state in its own file.
