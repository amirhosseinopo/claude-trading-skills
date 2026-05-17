"""Fetch the intraday tape for XAU/USD trading.

Primary: yfinance (no key) — gold via GC=F (futures, $1-3 from spot)
Optional upgrade: Twelve Data XAU/USD spot if TWELVEDATA_API_KEY env var is set

Usage:
    python fetch_tape.py                       # default 5m bars, 1 day window
    python fetch_tape.py --interval 1m --period 1d
    python fetch_tape.py --json                # machine-readable for orchestrator
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

# Tickers map: name -> yfinance symbol
TICKERS = {
    "gold":     "GC=F",       # gold futures, intraday spot proxy
    "dxy":      "DX-Y.NYB",   # dollar index
    "us10y":    "^TNX",       # 10Y yield × 10 (4.41 means 4.41%)
    "us30y":    "^TYX",       # 30Y yield × 10
    "vix":      "^VIX",       # equity vol
    "gvz":      "^GVZ",       # gold vol
    "spx":      "^GSPC",      # S&P 500
    "wti":      "CL=F",       # WTI crude futures
}

# ^TNX / ^TYX are already in percent form on yfinance (no rescale needed)


@dataclass
class Snapshot:
    name: str
    symbol: str
    last: float
    prev_close: float | None
    change_pct: float | None
    day_high: float | None
    day_low: float | None
    day_open: float | None
    bars: int
    last_bar_ts: str
    stale_minutes: int | None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def fetch_one(name: str, symbol: str, interval: str, period: str) -> Snapshot | None:
    """Fetch one ticker. Return None on failure rather than raise.

    Uses period=5d at the requested interval, then filters to the last
    calendar date for day_high/day_low/day_open. This works around yfinance
    returning empty for some indices at period=1d.
    """
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval,
                                        auto_adjust=False, prepost=True)
    except Exception:
        return None

    if df.empty:
        return None

    last       = float(df["Close"].iloc[-1])
    bars_total = len(df)
    last_ts    = df.index[-1]

    # Filter to last calendar date for "today's" stats
    last_date = last_ts.date()
    today_df  = df[df.index.date == last_date]
    if today_df.empty:
        today_df = df.tail(80)  # fallback: last 80 bars

    day_high = float(today_df["High"].max())
    day_low  = float(today_df["Low"].min())
    day_open = float(today_df["Open"].iloc[0])
    bars     = len(today_df)

    # Daily for prev_close
    try:
        d = yf.Ticker(symbol).history(period="5d", interval="1d")
        prev_close = float(d["Close"].iloc[-2]) if len(d) >= 2 else None
    except Exception:
        prev_close = None

    change_pct = None
    if prev_close and prev_close != 0:
        change_pct = (last - prev_close) / prev_close * 100

    # staleness
    try:
        last_ts_utc = last_ts.tz_convert("UTC") if last_ts.tzinfo else last_ts.tz_localize("UTC")
        stale = int((_now_utc() - last_ts_utc.to_pydatetime()).total_seconds() / 60)
    except Exception:
        stale = None

    return Snapshot(
        name        = name,
        symbol      = symbol,
        last        = round(last, 4),
        prev_close  = round(prev_close, 4) if prev_close is not None else None,
        change_pct  = round(change_pct, 3) if change_pct is not None else None,
        day_high    = round(day_high, 4),
        day_low     = round(day_low, 4),
        day_open    = round(day_open, 4),
        bars        = bars,
        last_bar_ts = str(last_ts),
        stale_minutes = stale,
    )


def fetch_xau_spot_twelvedata(api_key: str) -> dict[str, Any] | None:
    """If user set TWELVEDATA_API_KEY, prefer Twelve Data spot for XAU/USD.

    Free tier: 800 calls/day. Native XAU/USD symbol with 1m bars.
    Returns dict with last + day_high/low or None on failure.
    """
    import urllib.request, urllib.error
    url = ("https://api.twelvedata.com/quote"
           f"?symbol=XAU/USD&apikey={api_key}")
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    if data.get("status") == "error":
        return None
    try:
        return {
            "symbol":     "XAU/USD",
            "last":       float(data["close"]),
            "day_high":   float(data["high"]),
            "day_low":    float(data["low"]),
            "day_open":   float(data["open"]),
            "prev_close": float(data["previous_close"]),
            "change_pct": float(data["percent_change"]),
        }
    except (KeyError, ValueError, TypeError):
        return None


def fetch_intraday_bars(symbol: str, interval: str = "5m",
                        period: str = "1d") -> list[dict[str, float]]:
    """Return list of OHLCV bars for downstream FSM consumption."""
    df = yf.Ticker(symbol).history(period=period, interval=interval,
                                    auto_adjust=False, prepost=True)
    if df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        out.append({
            "ts":     str(ts),
            "open":   float(row["Open"]),
            "high":   float(row["High"]),
            "low":    float(row["Low"]),
            "close":  float(row["Close"]),
            "volume": float(row["Volume"]) if "Volume" in row else 0.0,
        })
    return out


def fetch_tape(interval: str = "5m", period: str = "1d") -> dict[str, Any]:
    """Fetch full tape. Returns a dict ready to dump as JSON."""
    snapshots: dict[str, Any] = {}
    for name, symbol in TICKERS.items():
        snap = fetch_one(name, symbol, interval, period)
        if snap is not None:
            snapshots[name] = asdict(snap)

    # Twelve Data upgrade for XAU spot
    td_key = os.environ.get("TWELVEDATA_API_KEY")
    if td_key:
        spot = fetch_xau_spot_twelvedata(td_key)
        if spot is not None:
            snapshots["xauusd_spot"] = spot

    return {
        "as_of":     _now_utc().isoformat(),
        "interval":  interval,
        "period":    period,
        "tickers":   snapshots,
        "td_used":   td_key is not None and "xauusd_spot" in snapshots,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--interval", default="5m",
                   choices=["1m", "2m", "5m", "15m", "30m", "60m"])
    p.add_argument("--period",   default="5d")
    p.add_argument("--json",     action="store_true",
                   help="emit JSON to stdout (for orchestrator pipes)")
    args = p.parse_args(argv)

    tape = fetch_tape(args.interval, args.period)

    if args.json:
        print(json.dumps(tape, indent=2))
        return 0

    # Human view
    print(f"AS OF {tape['as_of']}  interval={tape['interval']} period={tape['period']}")
    if tape["td_used"]:
        print("  (Twelve Data XAU/USD spot ACTIVE)")
    print()
    print(f"{'TICKER':14s} {'SYMBOL':10s} {'LAST':>10s} {'CHG %':>8s} "
          f"{'DAY LO':>10s} {'DAY HI':>10s} {'BARS':>5s} {'STALE':>7s}")
    print("-" * 90)
    for name, snap in tape["tickers"].items():
        if name == "xauusd_spot":
            print(f"{name:14s} {snap['symbol']:10s} {snap['last']:>10.4f} "
                  f"{snap.get('change_pct', 0):>+8.2f} {snap['day_low']:>10.4f} "
                  f"{snap['day_high']:>10.4f} {'(td)':>5s} {'live':>7s}")
            continue
        stale = f"{snap['stale_minutes']}m" if snap.get('stale_minutes') is not None else "?"
        chg   = snap.get('change_pct')
        chg_s = f"{chg:+8.2f}" if chg is not None else "       —"
        print(f"{name:14s} {snap['symbol']:10s} {snap['last']:>10.4f} "
              f"{chg_s} {snap['day_low']:>10.4f} {snap['day_high']:>10.4f} "
              f"{snap['bars']:>5d} {stale:>7s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
