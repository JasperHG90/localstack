# Trading System — OpenFang Hands

Three hands + one skill that form a complete advisory trading system on DEGIRO.

## Architecture

```
┌─────────────┐   agent_send    ┌──────────────────┐
│   Trader     │ ──────────────→│  Market Analyst   │
│   Advisor    │ ←──────────────│  (scoring engine) │
└──────┬───────┘   scored report └────────▲─────────┘
       │                                  │ agent_send
       │ telegram_send                    │
       ▼                          ┌───────┴──────────┐
  [Investor]                      │   Trend Scout     │
  via Telegram                    │  (opportunity     │
       ▲                          │   scanner)        │
       │ telegram_send            └──────────────────┘
       │
  [Stop Alerts]
  (4h price check)
```

| Hand | Purpose | Model | Schedule |
|---|---|---|---|
| `trader-advisor` | Session management, briefings, rule enforcement, BRIEF tickets | Gemini 3 Flash (OpenRouter) | Mon-Fri 06:00 UTC + 4h stop alerts |
| `market-analyst` | Independent bull/bear scoring engine | Gemini 3 Flash (OpenRouter) | On-demand via agent_send |
| `trend-scout` | Proactive opportunity scanner | Gemini 3 Flash (OpenRouter) | Tue/Fri 07:00 UTC |

| Skill | Purpose |
|---|---|
| `price` | Yahoo Finance quotes via `requests` (uv inline deps) |

## Deployment

All hands and skills register via `register.sh` during the standard OpenFang sync:

1. Skills install from `/tmp/skills/*/` via `openfang skill install`.
2. Hands upsert from `/tmp/hands/*/HAND.toml` via `/api/hands/upsert` + `openfang hand activate`.
3. Cron entries sync from `/tmp/schedules.json` — delete stale, recreate with current agent IDs.

After merging, run the sync so all four components register.

## Bootstrap

Only the trader-advisor needs bootstrapping. The other hands are stateless or derive context from the trader-advisor's KV.

**Option A — Seed MASTER via Telegram (recommended):**
Trigger the trader-advisor manually. If no MASTER key exists, it runs the onboarding flow: asks the investor for positions in a structured format, builds the table, writes to KV, confirms.

**Option B — Seed MASTER via developer tooling:**
```
memex_kv_write(
  key="app:openfang:trader-advisor:master",
  value="# MASTER — Current Positions & Cash\n\n| # | Instrument | Exchange | Yahoo Ticker | Shares | Entry | Stop (8%) | Target (75%) | Orders Live |\n|---|...|"
)
```

**Required setting:** `telegram_chat_id` on the trader-advisor hand.

## Schedules (9 total, 5 for trading)

| Name | Agent | Cron (UTC) | What it does |
|---|---|---|---|
| `trader-advisor-briefing` | trader-advisor-hand | `0 6 * * 2,3,5` | Full pre-market briefing (Tue/Wed/Fri) |
| `trader-advisor-trail-check` | trader-advisor-hand | `0 6 * * 1,4` | Full briefing + mandatory trailing stop review (Mon/Thu) |
| `trader-advisor-stop-alert` | trader-advisor-hand | `0 10,14,18 * * 1-5` | Lightweight 4h price check — Telegram alert only if within 2% of stop |
| `trend-scout-weekly` | trend-scout-hand | `0 7 * * 2,5` | Opportunity scan + market-analyst scoring (Tue/Fri) |

All crons are UTC. `06:00 UTC` = 07:00 Amsterdam winter / 08:00 summer (before 09:00 European open).

## State layout (memex KV)

All keys under `app:openfang:trader-advisor:*`:

| Key | Content |
|---|---|
| `master` | Authoritative MASTER positions table (markdown) |
| `last_briefing_ts` | ISO 8601 |
| `last_session_close_ts` | ISO 8601 |
| `portfolio_value_eur` | Computed from positions + cash |
| `cash_eur_total` | DEGIRO EUR cash |
| `open_positions_count` | Count |
| `positions_under_stop_pressure` | Count within 2% (updated by stop-alert) |
| `unresolved_open_questions_count` | Count |

Trend-scout keys under `app:openfang:trend-scout:*`:

| Key | Content |
|---|---|
| `last_run` | ISO 8601 |
| `last_themes` | Comma-separated themes scanned |
| `last_opportunities` | Comma-separated tickers surfaced |
| `last_digest_count` | Number of opportunities in last digest |

## DEGIRO / Yahoo Finance ticker mapping

The `price` skill uses Yahoo Finance tickers. The MASTER table must include a `Yahoo Ticker` column:

| Exchange | Suffix | Example |
|---|---|---|
| XETRA | `.DE` | `RHM.DE` |
| Euronext Amsterdam | `.AS` | `ASML.AS` |
| Euronext Paris | `.PA` | `HO.PA` |
| London | `.L` | `BA.L` |
| NASDAQ / NYSE | (none) | `NVDA` |

## Trailing stops on DEGIRO

DEGIRO has no native trailing stop. The system implements manual trailing:

1. **At entry**: trader-advisor produces a Stop Limit SELL ticket at the defined stop.
2. **Mon/Thu 06:00 UTC**: the `trail-check` schedule explicitly prompts the hand to compute new stops for every position using `current_price × (1 - trail%)`. If the new stop exceeds the existing one, an updated BRIEF ticket is produced.
3. **Stops only go up** (Rule 3). The hand refuses to lower one.
4. **Default trail**: 8% (configurable via `default_trail_percent` setting).

## Position sizing

When proposing a new entry, the hand computes:
- `risk_per_trade = portfolio_value × 2%`
- `shares = floor(risk_per_trade / (entry - stop))`
- `cost = shares × entry`
- `portfolio_weight = cost / portfolio_value`
- Warns if `portfolio_weight > 20%` (concentration) or `cost > cash` (insufficient funds).

## Mid-session MASTER updates

When the investor confirms a state change during a Telegram conversation ("stop placed", "order filled", "position closed"), the hand updates the MASTER KV key **immediately** — not at session close. This prevents state drift during long sessions.

## What these hands will never do

- Place orders on any platform.
- Lower a trailing stop.
- Touch crypto, forex, or leveraged/inverse products.
- Infer position state from chat history instead of reading the MASTER KV key.
- Recycle stale opportunity ideas (trend-scout checks previous run's tickers).
- Auto-confirm anything — all BRIEF tickets require the investor to act on DEGIRO.
