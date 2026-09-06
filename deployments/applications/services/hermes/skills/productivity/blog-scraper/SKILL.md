---
name: blog-scraper
description: Daily engineering blog scraper — visits top AI/eng blogs, extracts new articles verbatim, stores in OpenViking
version: 1.1.0
metadata:
  hermes:
    tags: [productivity, scraping, engineering, blogs, openviking]
    category: productivity
---
## When to Use

When running scheduled daily blog scrapes, or when asked to check engineering blogs for new articles.

## Configuration

- Use the native OpenViking tools (`viking_*`). Do not shell out to curl.
- "Which URLs have I already scraped?" needs EXACT-KEY reads, which OpenViking
  cannot do -- it is a semantic store. Keep the per-site URL lists in
  `$HERMES_HOME/state/blog-scraper.json` via the `files` toolset. Articles go
  to OpenViking.

## Critical Rules

- **NEVER summarize.** Save the full, verbatim article text as clean markdown. Partial summaries = failed capture.
- **NEVER write post-mortem notes yourself.** Report errors to a subagent with the `/post-mortem` skill.

## Target Blogs

1. https://www.anthropic.com/engineering
2. https://openai.com/news/engineering/
3. https://engineering.atspotify.com/
4. https://deepmind.google/
5. https://www.uber.com/nl/en/blog/engineering/
6. https://mistral.ai/fr/news/
7. https://ollama.com/blog
8. https://addyosmani.com/blog/

## Procedure

### Phase 1: Load State

For each blog, check previously scraped URLs:

```
read $HERMES_HOME/state/blog-scraper.json, take scraped["{site_key}"]
```

Site keys: `anthropic`, `openai`, `spotify`, `deepmind`, `uber`, `mistral`, `ollama`. Each value is a JSON array of URLs. Missing file or key = first run.

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
3. Add each image with its own `viking_add_resource(url=<image_url>)`

If image download fails, continue — save article text anyway.

### Phase 3: Save to OpenViking

For each new article:

```
viking_add_resource(
  url="{the article URL}",
  reason="blog-scraper capture from {source}: {actual article title from page}"
)
```

`viking_add_resource` fetches and parses the page itself, which is what keeps
the text verbatim. There is no upsert and no note key: idempotency comes from
the state file in Phase 1, so a URL you failed to record will be captured
twice.

### Phase 4: Update State

Update KV for each blog:

```
$HERMES_HOME/state/blog-scraper.json
  scraped["{site_key}"] = [updated JSON array]
```

Read-modify-write the whole file, or you will drop the other sites' lists.
Only keep URLs from the last 3 days; prune older entries on every write.

Also write:

```
$HERMES_HOME/state/blog-scraper.json
  last_run   = "{ISO-timestamp}"
  last_count = {new articles found}
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
