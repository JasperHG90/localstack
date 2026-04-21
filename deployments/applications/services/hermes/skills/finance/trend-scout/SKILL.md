---
name: trend-scout
description: Proactive opportunity scanner. Discovers investment themes, sector rotations, and catalyst-driven opportunities. Weekly digest via Telegram.
version: 1.0.0
metadata:
  hermes:
    tags: [finance, scanning, opportunities, themes, investing]
    category: finance
---
## When to Use

When running scheduled weekly opportunity scans, or when asked to find new investment ideas.

## Configuration

- KV namespace: `app:hermes:trend-scout:*`
- Memex API: `$MEMEX_SERVER_URL/api/v1`, auth `-H "X-API-Key: $MEMEX_API_KEY"`

## Procedure

### Phase 0 — Load Context

1. Read current exposure:
   ```
   curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:trader-advisor:master"
   ```
   Note which instruments, sectors, themes are already held.

2. Read tactical watchlist:
   ```
   curl -s -H "X-API-Key: $MEMEX_API_KEY" "$MEMEX_SERVER_URL/api/v1/kv/get?key=app:hermes:trader-advisor:tactical_watchlist"
   ```

3. Read own state (`last_run`, `last_themes`, `last_opportunities`) to avoid repeating ideas.

### Phase 1 — Broad Scan

Search across categories using `web_search` (15-20 searches total):

**Thematic** (aligned with investor's lens):
- European defence stocks catalyst, AI infrastructure, energy sector rotation
- Each tactical watchlist theme

**Macro-driven** (new themes):
- Sector rotation signals, best performing sectors, emerging market catalysts
- Commodities supply deficit, IPO calendar Europe

**Contrarian / dislocation:**
- Oversold stocks Europe, near 52-week low with strong fundamentals
- Analyst upgrades European equities

**Income / alternative:**
- High dividend stocks Europe DEGIRO, infrastructure ETF Europe

Read top articles via `web_fetch`. Only surface opportunities with **specific, time-bound catalysts**.

**Deep dives:** For the most promising 3-5 leads, delegate to a subagent with the `/researcher` skill:
```
Research {INSTRUMENT} ({EXCHANGE}): recent earnings, analyst revisions, competitive positioning, regulatory risks, catalyst expected in next 1-3 months. Depth: thorough. Output: brief.
```

### Phase 2 — Filter

Apply in order:
1. **Accessibility**: available on DEGIRO? If not, discard.
2. **No overlap**: already exposed? If so, discard unless new catalyst.
3. **Catalyst clarity**: specific catalyst within 1-3 months? Vague trends insufficient.
4. **Risk/reward**: defined entry/stop/target with 2:1+ reward-to-risk.

Target: 3-5 opportunities. Quality over quantity. Empty digest if nothing qualifies.

### Phase 3 — Score Each

For each filtered opportunity, delegate to a subagent with the `/market-analyst` skill:
```
ANALYSE: {TICKER} ({EXCHANGE})
THESIS: {the catalyst identified}
DEPTH: standard
```

**Only include BUY or STRONG_BUY verdicts** in the final digest.

### Phase 4 — Compose and Deliver

```
TREND SCOUT — {DD Month YYYY}

Scanned {N} sources across {M} themes.
{K} opportunities passed filters. {J} scored BUY or better.

---

{INSTRUMENT} ({EXCHANGE}) — {one-line thesis}
  Catalyst: {specific catalyst + timeframe}
  Verdict: {COMPOSITE}/100 → {VERDICT}
  Bull: {strongest point}
  Bear: {strongest counter}
  Suggested entry zone: {price range}
  DEGIRO accessible: Yes

---

These are research leads, not recommendations. Each requires defined entry/stop/target before capital is committed (Rule 1).
```

Send via Telegram. Split at 4096 chars if needed.

### Phase 5 — Persist State

Write to Memex KV:
- `app:hermes:trend-scout:last_run` → ISO timestamp
- `app:hermes:trend-scout:last_themes` → themes scanned
- `app:hermes:trend-scout:last_opportunities` → tickers surfaced
- `app:hermes:trend-scout:last_digest_count` → count in digest

## Constraints

- DEGIRO only — no crypto, forex, leveraged/inverse products
- Do not recycle ideas from previous run unless new catalyst emerged
- Batch scanner, not interactive advisor
- If market-analyst unavailable, present unscored with caveat

## Error Recovery

- web_search fails: skip category, note in digest
- market-analyst unavailable: present filtered without scores
- Telegram fails: persist as Memex note (vault: `trading`, tags: `trend-scout`, `digest`, `telegram-failed`)
- MASTER missing: scan without overlap filtering, note caveat

## Pitfalls

- Write in British English, cite sources with URLs
- Only specific, time-bound catalysts — not vague themes
- Must call market-analyst for scoring — do not self-score
