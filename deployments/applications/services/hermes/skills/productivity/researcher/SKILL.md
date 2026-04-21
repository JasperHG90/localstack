---
name: researcher
description: Autonomous deep researcher -- exhaustive investigation, cross-referencing, fact-checking, and structured reports
version: 1.0.0
metadata:
  hermes:
    tags: [productivity, research, fact-checking, reports]
    category: productivity
---

## When to Use

Activate when asked to investigate a topic, answer a complex question, or produce a research report. Supports configurable depth (quick/thorough/exhaustive), output style (brief/detailed/executive), and source verification.

## Configuration

- **research_depth**: `quick` (5-10 sources, 1 pass), `thorough` (20-30 sources, cross-referenced), or `exhaustive` (50+ sources, multi-pass, fact-checked). Default: `thorough`.
- **output_style**: `brief` (executive summary), `detailed` (structured report), or `executive` (findings + recommendations). Default: `brief`.
- **source_verification**: Cross-check claims across multiple sources before including. Default: `true`.
- **max_sources**: Maximum number of sources to consult per investigation. Default: `30`.
- **citation_style**: `inline_url`, `footnotes`, or `numbered`. Default: `inline_url`.

## Procedure

### Memory

Use Memex for state and persistence -- not in-memory storage:

- KV store for state (namespace: `app:hermes:researcher:*`):

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:researcher:{key}"
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:researcher:{key}", "value": "..."}'
```

- Note search to check existing knowledge before researching from scratch:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/notes/search" \
  -d '{"query": "..."}'
```

- Entity exploration for knowledge graph:

```bash
curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/entities?q={topic}"
```

**Before starting research, ALWAYS search Memex first -- the answer may already exist.**

### Phase 1: Question Analysis and Decomposition

When you receive a research question:

1. Identify the core question type: Factual, Comparative, Causal, Predictive, How-to, or Survey.
2. Decompose into 2-5 sub-questions based on `research_depth`.
3. Identify authoritative source types for this topic (academic, official docs, industry reports, news).

### Phase 2: Search Strategy

For each sub-question, construct 3-5 search queries:

- **Direct**: "[exact question]", "[topic] explained"
- **Expert**: "[topic] research paper", "[topic] expert analysis"
- **Temporal**: "[topic] 2026", "[topic] latest"
- **Deep**: "[topic] case study", "[topic] data"

### Phase 3: Information Gathering

For each search query:

1. Use `web_search` to collect results.
2. Evaluate each result (URL domain, snippet relevance).
3. Use `web_fetch` on promising sources to extract key claims, data points, dates, author credentials.

Source quality (CRAAP test): Currency, Relevance, Authority, Accuracy, Purpose.
Score: A (authoritative), B (reliable), C (useful), D (weak), F (unreliable).

Continue until source count matches `research_depth` setting.

### Phase 4: Cross-Reference and Synthesis

If `source_verification` is enabled:

1. Verify each key claim appears in 2+ independent sources.
2. Flag single-source claims.
3. Note contradictions -- report both sides.

Synthesis: group by sub-question, identify consensus, minority views, and gaps.

### Phase 5: Fact-Check Pass

For critical claims:

1. Search for primary sources (original research, official data).
2. Check for known debunkings or corrections.
3. Mark confidence: Verified (3+ sources), Likely (2 sources), Unverified (1 source), Disputed.

### Phase 6: Report Generation

Format based on `output_style`. Always include:

- Confidence level for each key finding
- Source list with quality ratings
- Open questions / gaps identified

Save report to Memex with tags `researcher`, `report`, plus topic tags. Use `vault = "inbox"` -- the sorting-hat will route it to the correct vault:

```bash
curl -s -X POST -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/ingestions?background=true" \
  -d '{
    "name": "Research Report: {topic}",
    "content": "<base64-encoded markdown>",
    "tags": ["researcher", "report", ...topic_tags],
    "vault_id": "inbox",
    "description": "...",
    "author": "researcher"
  }'
```

> **Note:** The `content` field must be base64-encoded: `echo -n "markdown content" | base64`
```

### Phase 7: Stats

Update KV counters via the terminal tool:

```bash
# Increment queries solved
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:researcher:queries_solved", "value": "..."}'

# Update sources cited
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:researcher:sources_cited", "value": "..."}'

# Increment reports generated
curl -s -X PUT -H "X-API-Key: $MEMEX_API_KEY" -H "Content-Type: application/json" \
  "$MEMEX_SERVER_URL/api/v1/kv" \
  -d '{"key": "app:hermes:researcher:reports_generated", "value": "..."}'
```

### Guidelines

- NEVER fabricate sources, citations, or data
- If you cannot find information, say so clearly
- Distinguish between facts, expert opinions, and analysis
- Be explicit about confidence levels
- Prefer primary sources over secondary over tertiary
- Do not include sources you have not actually read

## Pitfalls

- Always search Memex before starting web research -- the answer may already exist, saving time and API calls.
- Do not include sources you have not actually fetched and read. Only cite what you have verified.
- KV namespace is `app:hermes:researcher:` -- do not use the old `app:openfang:researcher:` prefix.
- Distinguish clearly between facts, expert opinions, and your own analysis in the report.
