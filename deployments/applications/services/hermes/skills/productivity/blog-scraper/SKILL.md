---
name: blog-scraper
description: Daily engineering blog scraper — visits top AI/eng blogs, extracts new articles verbatim, stores in Memex
version: 1.1.0
metadata:
  hermes:
    tags: [productivity, scraping, engineering, blogs, memex]
    category: productivity
---
## When to Use

When running scheduled daily blog scrapes, or when asked to check engineering blogs for new articles.

## Configuration

- KV namespace: `app:hermes:blog-scraper:*`
- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl.

## Critical Rules

- **NEVER summarize.** Save the full, verbatim article text as clean markdown. Partial summaries = failed capture.
- **NEVER write post-mortem notes to Memex.** Report errors to a subagent with the `/post-mortem` skill.

## Target Blogs

1. https://www.anthropic.com/engineering
2. https://openai.com/news/engineering/
3. https://engineering.atspotify.com/
4. https://deepmind.google/

## Procedure

### Phase 1: Load State

For each blog, check previously scraped URLs:

```
memex_kv_get(key="app:hermes:blog-scraper:scraped:{site_key}")
```

Site keys: `anthropic`, `openai`, `spotify`, `deepmind`. Value is JSON array of URLs. Missing key = first run.

### Phase 2: Scrape Each Blog

For each blog:
1. Use browser tools to visit the listing page and extract article links:
   - Navigate to the blog URL
   - Extract all article titles and URLs from the page
2. Compare against stored list. Only process NEW articles.
3. For each new article:
   - Navigate to the article page
   - Extract full content as clean markdown: title, author, date, complete body
   - List image URLs (diagrams, charts, technical figures — skip decorative)

### Phase 2b: Content Gate

Before saving, verify:
- Body is at least 1500 characters
- Does not contain bot-wall keywords ("security verification", "just a moment", "enable JavaScript")

If failed: skip article, report to subagent with `/post-mortem` skill.

### Phase 2c: Capture Assets

For successfully captured articles:
1. Parse for meaningful images (diagrams, charts, code screenshots)
2. Download via terminal: `curl -sL -A "Mozilla/5.0" -o /tmp/{uuid}.png {image_url}`
3. After creating the Memex note, attach images via `memex_add_assets(note_id=$NOTE_ID, ...)`

If image download fails, continue — save article text anyway.

### Phase 3: Save to Memex

For each new article:

```
memex_retain(
  title="{actual article title from page}",
  author="blog-scraper",
  description="{first sentence of article}",
  tags=["blog-scraper", "engineering", "{source}"],
  markdown_content=$FULL_VERBATIM_ARTICLE_MARKDOWN,
  vault_id="inbox",
  note_key="blog-scraper:article:{url_slug}",
  background=True
)
```

Capture the returned note id into `NOTE_ID` so downstream steps (asset attach) can reference it.

`markdown_content` is raw markdown (no base64 encoding). The `note_key` ensures idempotency. The body must include: source URL, author, date, complete article.

### Phase 4: Update State

Update KV for each blog:

```
memex_kv_write(
  key="app:hermes:blog-scraper:scraped:{site_key}",
  value="{updated JSON array}"
)
```

Only keep URLs from last 3 days. Remove older entries.

Also write:

```
memex_kv_write(key="app:hermes:blog-scraper:last_run", value="{ISO-timestamp}")
memex_kv_write(key="app:hermes:blog-scraper:last_count", value="{new articles found}")
```

## Error Handling

- Blog unreachable: skip it, report to `/post-mortem` subagent, continue with others
- Article page fails: skip that article
- Never fail the entire run because of one site or article
- Always extract REAL titles from HTML — never fabricate

## Pitfalls

- Use browser tools for JavaScript-rendered pages
- Content gate prevents saving bot-wall pages
- Note keys ensure no duplicate saves across runs
- 3-day TTL on scraped URL lists prevents unbounded growth
