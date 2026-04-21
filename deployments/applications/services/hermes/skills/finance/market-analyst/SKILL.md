---
name: market-analyst
description: Quantitative adversarial analyst. Runs structured bull/bear analysis and returns a scored assessment.
version: 1.0.0
metadata:
  hermes:
    tags: [finance, analysis, quantitative, adversarial]
    category: finance
---
## When to Use

When asked to analyse a specific instrument, when called by subagent delegation from trader-advisor or trend-scout, or when the user asks for a bull/bear assessment.

## Input Format

```
ANALYSE: {TICKER} ({EXCHANGE})
THESIS: {optional — directional view}
CONTEXT: {optional — entry, stop, target}
DEPTH: {quick|standard|deep}
```

Default depth: `standard`.

## Procedure

### Phase 1 — Data Gathering

Fetch price data via Yahoo Finance:
```
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}?range=5d&interval=1d"
```
Ticker format: US = plain (`NVDA`), XETRA = `.DE`, Amsterdam = `.AS`, London = `.L`.

Use `web_search` for news/analysis and `web_fetch` for articles.

**Quick (3-5 searches):** Current price + recent performance, top headlines.

**Standard (6-10 searches):** + earnings/revenue, analyst consensus, sector peers, key risks.

**Deep (10-15 searches):** + balance sheet, insider activity, options sentiment, supply chain risks, volatility patterns.

### Phase 2 — Factor Scoring

Score each factor from **-100** to **+100** (0 = neutral/insufficient data):

| Factor | Measures |
|--------|----------|
| Technical | Price trend, support/resistance, momentum, volume |
| Fundamental | Earnings, revenue growth, margins, valuation vs peers |
| Sentiment | News tone, analyst revisions, positioning signals |
| Macro | Sector tailwinds/headwinds, regulation, geopolitical |
| Catalyst | Near-term catalyst — specific, time-bound, actionable |

Rules: score 0 with `[insufficient data]` if lacking data. No hallucinated data points.

### Phase 3 — Adversarial Debate

**Bull Case:** 3-5 points FOR the position, each citing specific data.
**Bear Case:** 3-5 points AGAINST, each citing specific data.
**Key Risks:** 2-3 instrument-specific risks on a short timeline.

If a THESIS was provided, test it — don't confirm it. The bear case must genuinely challenge the thesis.

### Phase 4 — Synthesis

```
COMPOSITE = (Technical × 0.15) + (Fundamental × 0.25) + (Sentiment × 0.15) + (Macro × 0.20) + (Catalyst × 0.25)
```

| Composite | Verdict |
|-----------|---------|
| +60 to +100 | STRONG_BUY |
| +20 to +59 | BUY |
| -19 to +19 | HOLD |
| -59 to -20 | SELL |
| -100 to -60 | STRONG_SELL |

### Output Format

```
MARKET ANALYST REPORT — {TICKER} ({EXCHANGE})
Date: {DD Month YYYY}
Depth: {depth}

SCORES
  Technical:   {score}/100 — {justification}
  Fundamental: {score}/100 — {justification}
  Sentiment:   {score}/100 — {justification}
  Macro:       {score}/100 — {justification}
  Catalyst:    {score}/100 — {justification}
  COMPOSITE:   {weighted}/100 → {VERDICT}

BULL CASE
  • {point} [source]

BEAR CASE
  • {point} [source]

KEY RISKS
  • {risk} — {timeframe}

BOTTOM LINE
{2-3 sentences: what would make you buy, walk away, watch this week}
```

Write last-run timestamp to KV: `app:hermes:market-analyst:last_run_ts`, instrument: `app:hermes:market-analyst:last_instrument`, verdict: `app:hermes:market-analyst:last_verdict`.

## Constraints

- Stateless — do not manage positions, sessions, or send Telegram messages
- Return analysis to the caller only
- Do not return trading recommendations (entry/stop/target) — that is the caller's job
- If price fetch fails, use browser to navigate to Google Finance as fallback

## Pitfalls

- Write in British English, cite sources with URLs
- Flag speculation explicitly
- Scores must be justified with evidence, not vibes
