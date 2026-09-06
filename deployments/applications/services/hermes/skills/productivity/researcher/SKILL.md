---
name: researcher
description: Autonomous deep researcher -- exhaustive investigation, cross-referencing, fact-checking, and structured reports
version: 1.1.0
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
- Use the native OpenViking tools (`viking_*`). Do not shell out to curl.
- Counters and run state need EXACT-KEY reads, which OpenViking cannot do --
  it is a semantic store. Keep them in `$HERMES_HOME/state/researcher.json`
  via the `files` toolset.

## Procedure

### Memory

Use OpenViking for state and persistence -- not in-memory storage:

- KV store for state (namespace: `app:hermes:researcher:*`):

```
read/write $HERMES_HOME/state/researcher.json
```

- Search existing knowledge before researching from scratch:

```
viking_search(query="{topic}", mode="deep", limit=20)
viking_read(uri="<a uri the search returned>", level="overview")
```

  One search, not two: OpenViking has a single semantic index rather than
  separate note and memory planes. Start at `level="abstract"` and go deeper
  only for the few hits that look load-bearing.

- There is no entity graph and no co-occurrence lookup. To explore around a
  topic, search for the relation you want in words:

```
viking_search(query="{topic} and the systems or people it depends on", mode="deep")
```

  This is genuinely weaker than a graph walk: it will not enumerate every
  neighbour, and it will not tell you two things co-occur. Say so in the
  report rather than implying completeness.

**Before starting research, ALWAYS search OpenViking first -- the answer may already exist.**

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

Save report to OpenViking with tags `researcher`, `report`, plus topic tags. Use `vault_id="inbox"` -- the sorting-hat will route it to the correct vault:

```
viking_remember(
  content=$REPORT_MARKDOWN,   # first line: Research Report: {topic}
  category="case"
)
```

`category="case"` -- a research report is a worked-through question. Put the
topic in the first line: it is what makes the report findable later, since
there are no tags and no title field.

### Phase 7: Stats

Update the counters, read-modify-write on the whole file:

```
$HERMES_HOME/state/researcher.json
  queries_solved    += 1
  sources_cited     += {count}
  reports_generated += 1
```

### Guidelines

- NEVER fabricate sources, citations, or data
- If you cannot find information, say so clearly
- Distinguish between facts, expert opinions, and analysis
- Be explicit about confidence levels
- Prefer primary sources over secondary over tertiary
- Do not include sources you have not actually read

## Pitfalls

- Always search OpenViking before starting web research -- the answer may already exist, saving time and API calls.
- Do not include sources you have not actually fetched and read. Only cite what you have verified.
- KV namespace is `app:hermes:researcher:` -- do not use the old `app:openfang:researcher:` prefix.
- Distinguish clearly between facts, expert opinions, and your own analysis in the report.
