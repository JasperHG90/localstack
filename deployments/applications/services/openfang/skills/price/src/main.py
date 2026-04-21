#!/usr/bin/env python3
"""Price skill for OpenFang — fetches live stock/ETF quotes from Yahoo Finance.
Uses stdlib only (urllib.request) — no external dependencies."""
import json, sys, urllib.request, urllib.error, urllib.parse

payload = json.loads(sys.stdin.read())

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OpenFang/1.0)"}


def _fetch_quote(ticker: str) -> dict:
    url = YAHOO_CHART.format(ticker=urllib.parse.quote(ticker))
    url += "?" + urllib.parse.urlencode({"interval": "1d", "range": "5d"})
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"ticker": ticker, "error": f"HTTP {e.code}", "hint": "Try browser hand or web_search as fallback"}
    except urllib.error.URLError as e:
        return {"ticker": ticker, "error": str(e.reason), "hint": "Network unreachable"}
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    results = data.get("chart", {}).get("result")
    if not results:
        err = data.get("chart", {}).get("error", {})
        return {"ticker": ticker, "error": err.get("description", "No data returned")}

    meta = results[0].get("meta", {})
    price = meta.get("regularMarketPrice")
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

    change_pct = None
    if price is not None and prev_close:
        change_pct = round((price - prev_close) / prev_close * 100, 2)

    return {
        "ticker": ticker,
        "price": price,
        "currency": meta.get("currency", "USD"),
        "exchange": meta.get("exchangeName", ""),
        "previous_close": prev_close,
        "change_pct": change_pct,
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
        "market_state": meta.get("marketState", "UNKNOWN"),
    }


def price_get_quote(args: dict) -> dict:
    ticker = args.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "ticker is required"}
    return _fetch_quote(ticker)


def price_get_quotes(args: dict) -> dict:
    tickers = args.get("tickers", [])
    if not tickers:
        return {"error": "tickers list is required"}
    return {"quotes": [_fetch_quote(t.strip().upper()) for t in tickers]}


TOOLS = {
    "price_get_quote": price_get_quote,
    "price_get_quotes": price_get_quotes,
}

handler = TOOLS.get(payload["tool"])
if not handler:
    print(json.dumps({"error": f"Unknown tool: {payload['tool']}"}))
else:
    print(json.dumps(handler(payload.get("input", {}))))
