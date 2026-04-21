---
name: medium-reader
description: Receives Medium digest emails, filters clickbait, and captures worthy articles verbatim to Memex inbox via archive sources
version: 1.0.0
metadata:
  hermes:
    tags: [productivity, medium, curation, articles, memex]
    category: productivity
---

## When to Use

Activate when you receive a Medium digest email containing article links and summaries. The skill evaluates each article, filters out clickbait, and captures worthy articles **verbatim** to the Memex inbox vault.

## Procedure

### Critical Rules

- **NEVER summarize.** Save the full, verbatim article text as clean markdown. If the full text cannot be captured, the task is a failure -- do not save partial summaries.
- **NEVER write post-mortem or retro notes to Memex.** Delegate errors to a subagent with the /post-mortem skill instead.

### Step 1: Extract Article Links

Parse the email content for Medium article URLs. These typically look like:

- `https://medium.com/...`
- `https://<publication>.medium.com/...`
- Custom publication domains (e.g. `pub.towardsai.net`, `betterprogramming.pub`)
- URLs with `?source=email` or similar tracking parameters

Ignore non-article links: unsubscribe, preferences, Medium homepage, tracking pixels, social media links.

For each article, note the URL and any title/description visible in the email.

### Step 2: Filter Clickbait

For each article, evaluate the title and description from the email.

**SKIP if any of these patterns match:**

- Numbered listicles: "10 things...", "5 libraries...", "7 ways...", "Top N..."
- Superlative bait: "you NEED to know", "mind-blowing", "game-changer", "will change everything"
- Engagement bait: "went feral", "destroyed", "I can't believe", "shocking"
- Vague promotional content with no technical substance
- Pure opinion pieces with no informational value
- "Versus" articles that are thinly veiled product promotions

**KEEP if:**

- Genuine technical content, research findings, or architecture deep-dives
- Tutorial or how-to with specific technical scope
- Analysis of a specific technology, paper, or system design
- Postmortem, case study, or lessons learned
- Significant open-source release or research paper announcement

### Step 3: Check for Duplicates

For each article that passes the filter:

1. Generate the idempotency key: `medium-reader:article:<url_slug>` where `<url_slug>` is derived from the article URL (strip protocol, replace `/` with `-`, remove query params). This key MUST be generated BEFORE any navigation.

2. Check if already captured:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:medium-reader:article:{url_slug}"
```

If it exists, skip this article.

### Step 4: Capture Article

For each new worthy article, attempt sources in this order. If one fails (bot wall, empty page, "Security Verification", "Just a moment"), do NOT retry the same URL -- immediately move to the next source:

1. `https://archive.is/<original_url>`
2. `https://web.archive.org/web/<original_url>`
3. `https://webcache.googleusercontent.com/search?q=cache:<original_url>`
4. Direct URL as last resort

For whichever source succeeds:

1. Use `browser_navigate` to load the URL, then `browser_snapshot` to read rendered content.
2. Extract from the page:
   - **Title**: from `<h1>`, `<title>`, or `og:title`. Never invent titles.
   - **Author**: from byline or article metadata if available.
   - **Date**: publication date if visible.
   - **Body**: the FULL article text converted to clean, verbatim markdown. NEVER summarize.

3. **Content gate**: if the extracted body is less than 1500 characters or contains "security verification" / "just a moment" keywords, the capture failed. Skip this article and delegate the error to a subagent with the /post-mortem skill.

### Step 4b: Capture Assets

For each successfully captured article, BEFORE saving to Memex:

1. Parse the page content for images. Skip avatars, tracking pixels, and decorative images. Keep diagrams, charts, code screenshots, and technical figures.
2. Download each image using the terminal tool:

```bash
curl -sL -A "Mozilla/5.0 (X11; Linux x86_64)" -o /tmp/{uuid}.png {image_url}
```

If image download fails, continue -- save the article text anyway. Missing assets are not a reason to skip the article.

### Step 4c: Save to Memex

Create the note:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/ingestions?background=true" \
  -d '{
    "name": "{extracted article title, verbatim from the page}",
    "content": "<base64-encoded markdown>",
    "tags": ["medium-reader", "medium", "{publication-slug}"],
    "vault_id": "inbox",
    "description": "One-sentence summary of the article",
    "note_key": "medium-reader:article:{url_slug}",
    "author": "medium-reader"
  }'
```

> **Note:** The `content` field must be base64-encoded: `echo -n "{full verbatim markdown with source URL, author, date, and complete body text}" | base64`
```

The `key` field MUST match the idempotency key generated in Step 3. This is mandatory for deduplication.

After creating the note, attach any downloaded assets from Step 4b.

Mark as processed:

```bash
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:medium-reader:article:{url_slug}", "value": "captured:{ISO-timestamp}", "ttl_seconds": 259200}'
```

### Step 5: Summary

After processing all articles, briefly report what you did:

- How many articles were in the email
- How many were skipped (with reasons)
- How many were captured

### Error Handling

- If all sources fail for an article (bot detection on every source): skip it, delegate to a subagent with the /post-mortem skill, continue with others.
- If note creation fails for one article: continue with remaining articles.
- Never fail the entire run because of one article.
- Never retry a URL that returned a bot wall or security page. Move to the next source immediately.

When you encounter errors (bot detection, asset capture failures, content extraction failures, Memex save failures), delegate to a subagent with the /post-mortem skill describing the issue. Include what went wrong, the root cause if identifiable, and a suggested fix. Do NOT write your own post-mortem notes to Memex. Only report actual failures, not clean runs.

## Pitfalls

- The idempotency key MUST be generated before any browser navigation. If you navigate first and then generate the key, you risk duplicate captures on retries.
- Never summarize article content. The entire value of this skill is verbatim capture. Partial summaries are considered failures.
- The content gate (1500 chars minimum, no bot-wall keywords) is critical -- without it, you will save garbage pages from bot walls.
- KV namespace is `app:hermes:medium-reader:` -- do not use the old `app:openfang:medium-reader:` prefix.
- KV entries for processed articles have a 3-day TTL (259200 seconds). This is intentional -- it prevents indefinite state growth while still preventing duplicates within a reasonable window.
