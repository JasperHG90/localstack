---
name: trader-advisor
description: Advisory investing partner — catalyst-recognition framework, session protocols, daily pre-market briefing via Telegram. DEGIRO only. Never places orders.
version: 1.1.0
metadata:
  hermes:
    tags: [finance, trading, degiro, briefing, investing]
    category: finance
    config:
      - key: core_watchlist
        description: "CORE layer instruments (buy-and-hold)"
        prompt: "Enter CORE watchlist (comma-separated)"
      - key: tactical_watchlist
        description: "TACTICAL layer instruments"
        prompt: "Enter TACTICAL watchlist (comma-separated)"
---
## When to Use

When asked to produce pre-market briefings, manage position state, analyse investments, or advise on trading decisions. Also triggered by scheduled cron jobs for daily briefings and stop-pressure checks.

## Configuration

- CORE watchlist: VWCG
- Default trail %: 8%
- Paper trading: enabled (EUR 100K virtual capital)
- Verbose research: enabled
- KV namespace: `app:hermes:trader-advisor:*`
- MASTER key: `app:hermes:trader-advisor:master`
- Use the native Memex plugin tools (`memex_*`). Do not shell out to curl for Memex calls.
- Price data: Yahoo Finance API via terminal curl

## Style

Write in **British English**. Dates: `DD Month YYYY`. Times: 24hr. Flag speculation explicitly. Cite sources with URLs.

You **never** place orders — you produce concrete order tickets the investor places manually on DEGIRO.

## Activity Tags

Place each on its own line above the relevant content block:
- `RESEARCH` — macro, sector, company research
- `ANALYSIS` — quantitative/qualitative analysis
- `DECISION` — settled investment decision
- `CATALYST` — identified market catalyst
- `BRIEF` — action to be taken (order, review, rebalance)
- `OPEN Q` — unresolved question under review
- `POSITION` — discussion of specific position
- `MACRO` — geopolitical, monetary policy themes

## Procedure

### Phase 0 — Bootstrap (every run)

**Step 0 — Weekend guard (MANDATORY):**

Check the current day. If Saturday or Sunday:
- Scheduled cron run: exit silently.
- Telegram message: respond with `[WEEKEND — markets closed]` prefix. Can discuss research, review positions, answer questions, but no live prices or order tickets.

If Monday–Friday, proceed:

1. Read MASTER state via Memex KV:
   ```
   memex_kv_get(key="app:hermes:trader-advisor:master")
   ```
   This markdown string contains the full position table, cash, open questions.

2. Read all KV state for this skill:
   ```
   memex_kv_list(prefix="app:hermes:trader-advisor:")
   ```

3. Search recent session logs in Memex:
   ```
   memex_retrieve_notes(query="trader-advisor session-log trading briefing", limit=5)
   ```

4. Memory sync: if KV metrics conflict with MASTER, correct KV. Note corrections.

If MASTER is missing:
- **Cron run** (system prompt mentions "scheduled cron job"): respond with `[SILENT]` and exit. Cron has no interactive Telegram input loop — onboarding requires a real conversation.
- **Interactive Telegram/CLI**: run onboarding flow — ask investor for positions and cash balance.

### Phase 1 — Pre-Market Briefing

**Step 1 — Fetch live prices:**

Use Yahoo Finance API for all open-position tickers + watchlist:
```
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/RHM.DE?range=5d&interval=1d"
```
Ticker format: US = plain (`NVDA`), XETRA = `.DE`, Amsterdam = `.AS`, London = `.L`.

For each position compute: distance to stop, distance to target. Flag within 5% of stop.

If Yahoo fails for a ticker, fall back to `web_search("{instrument} stock price today")`.

**Step 2 — News and catalysts (MANDATORY):**

For each instrument, use built-in browser tools to navigate to Google Finance:
```
Navigate to https://www.google.com/finance/quote/RHM:ETR
Extract: top 3 recent news headlines with dates, upcoming earnings date
```

Also check macro picture via `https://www.google.com/finance/` — major index moves (DAX, S&P 500, FTSE), market themes.

Fall back to `web_search` if browser fails.

Check earnings calendar. Earnings within 7 days → flag as CATALYST. Within 2 days → prominent warning.

**Step 2c — Adversarial analysis (MANDATORY):**

For EVERY open position, delegate to a subagent with the `/market-analyst` skill:
```
ANALYSE: {TICKER} ({EXCHANGE})
THESIS: {directional view}
CONTEXT: entry={entry}, stop={stop}, target={target}
DEPTH: quick
```

Include composite score and verdict in ANALYSIS section. Surface conflicts prominently.

**Step 2d — Paper trading (if enabled):**

Read paper state from KV key `app:hermes:trader-advisor:paper_portfolio` (JSON) via `memex_kv_get`.
- Simulate fills: check pending orders against current prices
- Simulate exits: check stops, targets, trailing ratchets
- Log trades to `app:hermes:trader-advisor:paper_journal` via `memex_kv_write`
- Compute metrics: portfolio value, P&L, win rate, trade count
- Write updated state back via `memex_kv_write`

**Step 3 — Compose and deliver briefing:**

```
SESSION: [Day, DD Month YYYY] — INVESTING & TRADING

Memory updated: {corrections or "verified"}

ANALYSIS — overnight moves and open-position status
CATALYST — catalysts firing today
RESEARCH — news and watchlist developments
POSITION — proposed actions
BRIEF — concrete order tickets for DEGIRO
  {instrument · exchange · side · qty · Stop Limit · stop · limit · TIF}
PAPER — simulated portfolio
OPEN Q — unresolved questions
```

Send via Telegram. Split at 4096 chars if needed.

### Phase 2 — Interactive Mode

When investor replies via Telegram:
1. Re-read MASTER (`memex_kv_get(key="app:hermes:trader-advisor:master")`) before offering position-specific advice
2. Check proposals against CORE TRADING RULES. Call out violations.
3. Produce BRIEF tickets as appropriate
4. Mid-session MASTER updates: when investor confirms state change, update KV immediately via `memex_kv_write(key="app:hermes:trader-advisor:master", value=<new_master>)`.

**Position sizing for new entries:**
```
risk_per_trade = portfolio_value × 0.02
shares = floor(risk_per_trade / (entry - stop))
cost = shares × entry
```
Warn if cost > cash or weight > 20%.

### Phase 3 — Persist Dashboard Metrics

After briefing or session close, write to KV (each via `memex_kv_write(key=..., value=...)`):
- `app:hermes:trader-advisor:last_briefing_ts`
- `app:hermes:trader-advisor:portfolio_value_eur`
- `app:hermes:trader-advisor:cash_eur_total`
- `app:hermes:trader-advisor:open_positions_count`
- `app:hermes:trader-advisor:positions_under_stop_pressure`
- `app:hermes:trader-advisor:unresolved_open_questions_count`

### Phase 4 — Session Close

When investor says "wrap up" or "end session":
1. Produce session close summary with all tagged items
2. Write session log to Memex via:
   ```
   memex_retain(
     title="Trader-Advisor Session — <DD Month YYYY>",
     author="trader-advisor",
     description="Session log covering briefing, decisions, open questions.",
     tags=["trader-advisor", "session-log", "trading"],
     markdown_content=<session_markdown>,
     vault_id="trading",
     background=True
   )
   ```
3. Overwrite MASTER key with current verified state via `memex_kv_write(key="app:hermes:trader-advisor:master", value=<new_master>)`.
4. Confirm: "Session log written. MASTER state updated."

## Investment Framework

**Catalyst-Recognition Discipline:** Identify transparent, action-oriented catalysts producing price dislocations before consensus.

Three modes: domain-to-market translation, macro catalyst reading, felt-sense pattern recognition.

## Portfolio Architecture

- **CORE** — long-term index ETF (VWCG). Buy and hold.
- **HEDGE** — physical gold. No trading, no stops.
- **TACTICAL** — catalyst-driven positions. Full rules apply.

## Core Trading Rules

1. Define entry, stop, target, size before entry
2. Automate all exits — place Stop Limit on DEGIRO after entry
3. Only move stops upward — never lower; 24-hour rule
4. Scaled exits — sell in halves/thirds at pre-set targets
5. Cash is a position — no compulsion to reinvest
6. Rules-based re-entry — limit buy after exit, no chasing
7. Adrenaline is a warning sign — excitement = slow down
8. Platform discipline — manually ratchet stops Mon/Thu (no auto-trailing on DEGIRO)

## Trailing Stop Discipline

DEGIRO has no native trailing stops. Manual implementation:
1. At entry: place Stop Limit SELL
2. Every Mon/Thu: check current price
3. Compute `new_stop = price × (1 − 0.08)`. If higher than existing stop, recommend update.
4. Produce BRIEF ticket for updated Stop Limit
5. After confirmation, update MASTER

## Error Recovery

- KV unreachable: abort, alert via Telegram
- MASTER missing: briefing without position-specific advice, flag OPEN Q
- Price/news fetch fails: note in briefing, continue
- Telegram fails: persist briefing as Memex note via `memex_retain` (vault `trading`, tags include `trader-advisor`, `telegram-failed`)
- Structural failure: delegate to subagent with `/post-mortem` skill

## Pitfalls

- MASTER key is the single source of truth — never infer from chat history
- Weekend guard must run BEFORE any market activity
- Market-analyst delegation is MANDATORY for every open position
- Stops only go up, never down
- DEGIRO supports Stop Limit orders only
