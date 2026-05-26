---
name: insight-linker
description: Connects recent Memex insights to GitHub projects by opening issues or PRs with actionable suggestions
version: 1.1.0
metadata:
  hermes:
    tags: [knowledge, github, insights, automation]
    category: knowledge
---

## When to Use

Activate on a schedule to scan recent Memex notes (blog posts, articles, research) and create GitHub issues or PRs when an insight contains an actionable technique, tool, pattern, or best practice applicable to a target repository.

## Configuration

- **github_user**: GitHub username for API access (default: `JasperHG90`)
- **github_repos**: Comma-separated list of `owner/repo` pairs to suggest improvements for (default: `JasperHG90/skills`)
- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl for Memex calls. (GitHub API access still uses `gh`/curl.)

## Procedure

### Phase 1: Discover Projects

For each repo in the `github_repos` list:

1. Check KV for cached repo context:

```
memex_kv_get(key="app:hermes:insight-linker:repo:<owner>/<repo>:context")
```

2. If cached and less than 7 days old, use the cached description. Otherwise, use `gh` CLI or GitHub API to get:
   - Repository metadata (language, topics, description)
   - README content
   - Summarize the repo's purpose, tech stack, and areas where improvements could apply.
   - Cache in KV:

```
memex_kv_write(
  key="app:hermes:insight-linker:repo:<owner>/<repo>:context",
  value="<summary + ISO timestamp>"
)
```

Build a mental map of what each project does and what kind of insights would be relevant.

### Phase 2: Search for Recent Insights

1. Get the last run timestamp:

```
memex_kv_get(key="app:hermes:insight-linker:last_run")
```

2. Search for recent notes since last run (or last 3 days on first run):

```
memex_retrieve_notes(
  query="engineering techniques tools patterns best practices",
  after="<lookback_date>"
)
```


3. Deduplicate by note ID.
4. Check which notes have already been processed:

```
memex_kv_list(prefix="app:hermes:insight-linker:processed:")
```

5. Filter out already-processed note IDs.

If no new notes remain, skip to Phase 5.

### Phase 3: Evaluate and Match

For each unprocessed note:

1. Read the note content. For small notes use `memex_read_note(note_id=<id>)` (only when total_tokens < 500). Otherwise get page indices first, then batch-fetch nodes:

```
memex_get_page_indices(note_ids=["<note_id>"])
memex_get_nodes(node_ids=["<node_id_1>", "<node_id_2>"])
```

2. Extract actionable insights. An insight is actionable if it describes:
   - A technique, pattern, or best practice that could improve a project
   - A tool, library, or framework that a project could adopt
   - A research finding with practical implications
   - A security practice, testing approach, or workflow improvement
   - An architectural pattern or design principle

3. For each actionable insight, match it to one or more target repos:
   - Does the repo's tech stack align with the insight?
   - Would the repo benefit from this technique/tool/pattern?
   - Is the suggestion substantial enough to warrant an issue?

4. **Skip if:**
   - The insight is too vague or generic to be actionable
   - The insight doesn't apply to any target repo
   - The suggested improvement is trivial or already likely implemented
   - The note is just a news announcement with no technique to apply

5. For each valid match, draft an issue (or PR):
   - **Issue title**: concise, actionable (e.g. "Adopt adversarial review process for prompt evaluation")
   - **Issue body**: structured markdown with:
     - **Context**: what insight prompted this (link to source article if available)
     - **Suggestion**: what to do and why
     - **Relevance**: why this applies to this specific project
     - **References**: source URL, related resources
   - Add label `insight-linker` to all created issues for traceability.

### Phase 4: Create Issues / PRs

#### Creating an Issue

1. Ensure the label exists:

```bash
gh label create "insight-linker" --color "7057ff" --description "Suggested by the Insight Linker skill" --repo "{owner}/{repo}" --force
```

2. Check for duplicates before creating:

```bash
gh issue list --repo "{owner}/{repo}" --label "insight-linker" --state open
```

Skip if a similar issue already exists.

3. Create the issue:

```bash
gh issue create --repo "{owner}/{repo}" --title "{title}" --body "{body}" --label "insight-linker"
```

#### Creating a PR (for simple, self-contained changes)

Only create a PR when the change is:
- A single file addition or edit
- Self-contained (no dependencies on other changes)
- Low-risk (documentation, config, non-breaking additions)

**Prefer issues over PRs.** Only create a PR when you are confident the change is correct and complete. If any step fails, fall back to creating an issue instead.

### Phase 5: Update State

1. For each processed note:

```
memex_kv_write(
  key="app:hermes:insight-linker:processed:<note_id>",
  value="<action>:<ISO-timestamp>"
)
```

Where `action` is `issue`, `pr`, or `skipped`.

2. Update last run and issue count:

```
memex_kv_write(key="app:hermes:insight-linker:last_run", value="<ISO-timestamp>")
memex_kv_write(key="app:hermes:insight-linker:last_issues", value="<count>")
```

### Quality Guidelines

- **Be selective.** Not every article warrants an issue. Only create issues for genuinely useful, applicable insights.
- **Be specific.** "Consider using X" is weak. "Adopt X for Y because Z, as described in [article]" is useful.
- **Respect the project.** Read the repo README to understand conventions before suggesting changes.
- **One issue per insight per repo.** Do not spam multiple issues from the same article.
- **Link back to sources.** Always include the article/note title and source URL in the issue body.

### Error Handling

- If GitHub API returns 403 (rate limit): stop creating issues, log error, skip to Phase 5.
- If a specific repo is not found (404): skip it, continue with others.
- If issue creation fails: log error, continue with remaining insights.
- Never fail the entire run because of one repo or one note.

When you encounter errors during your run (GitHub API rate limits, repo not found, issue creation failures, Memex search failures), delegate to a subagent with the /post-mortem skill describing the issue. Include what went wrong, the root cause if identifiable, and a suggested fix. Do NOT report clean runs or "no new insights found."

## Pitfalls

- Always check for duplicate issues before creating new ones -- the `insight-linker` label filter is the deduplication mechanism.
- Do not create PRs unless the change is trivially correct. Issues are safer and more appropriate for suggestions.
- KV namespace is `app:hermes:insight-linker:` -- do not use the old `app:openfang:insight-linker:` prefix.
- Cache repo context for 7 days to avoid redundant GitHub API calls.
