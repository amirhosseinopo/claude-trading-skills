"""Detect intraday XAU/USD setups from 5-min bars.

Three patterns evaluated each call. Each can emit:
    DORMANT      - precondition not met
    ARMED        - precondition met, awaiting trigger candle
    TRIGGERED    - emit signal with entry/stop/target
    INVALIDATED  - precondition met then broken, do not enter

Patterns:
    P1: NY-ORL Break (long or short)
        ORL = first 6 bars (30min) of NY session 13:30-14:00 UTC
        Trigger long  = 5m close > ORH with body > 0.3×ATR
        Trigger short = 5m close < ORL with body > 0.3×ATR
    P2: Failed Breakout Fade
        Reference high = max of today excluding last 2 bars
        Armed when last 2 bars print above reference high
        Triggered short when 5m close back below ref high
    P3: Trend Continuation
        Higher-highs + higher-lows over last 6 bars = up-trend
        Pullback to last swing low + bullish reversal candle = long
        Symmetric for down-trend.

Usage:
    python detect_setup.py                  # human view
    python detect_setup.py --json
    python detect_setup.py --bars path.json # use bars from disk
"""
from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
from dataclasses import asdict, dataclass

# Force UTF-8 stdout on Windows (cp1252 default chokes on Unicode arrows etc.)
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, time, timezone
from typing import Any

# Allow import-as-module without yfinance in caller
try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False


NY_OPEN_UTC  = time(13, 30)  # 9:30 ET
NY_CLOSE_UTC = time(20, 0)   # 16:00 ET
ORL_BARS     = 6             # 6 × 5min = first 30min of NY session


@dataclass
class Setup:
    name: str
    state: str             # DORMANT | ARMED | TRIGGERED | INVALIDATED
    side: str | None       # LONG | SHORT | None
    entry: float | None
    stop: float | None
    target1: float | None
    target2: float | None
    rr1: float | None
    notes: str


def _atr(bars: list[dict], n: int = 14) -> float:
    """True Range average over last n bars (simple, not Wilder-smoothed)."""
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    return statistics.mean(trs[-n:]) if trs else 0.0


def _ny_session_bars(bars: list[dict]) -> list[dict]:
    """Return bars whose timestamp falls within today's NY session."""
    if not bars:
        return []
    last_ts = _parse_ts(bars[-1]["ts"])
    last_date = last_ts.date()
    out = []
    for b in bars:
        ts = _parse_ts(b["ts"])
        if ts.date() == last_date and NY_OPEN_UTC <= ts.time() <= NY_CLOSE_UTC:
            out.append(b)
    return out


def _parse_ts(s: str) -> datetime:
    # yfinance ts strings look like "2026-05-12 11:05:00-04:00"
    return datetime.fromisoformat(s)


def detect_p1_ny_orl_break(bars: list[dict], atr: float) -> Setup:
    ny = _ny_session_bars(bars)
    if len(ny) < ORL_BARS:
        return Setup("P1 NY-ORL Break", "DORMANT", None, None, None, None, None, None,
                     f"NY session not yet open or < {ORL_BARS} bars in; have {len(ny)}")

    or_bars = ny[:ORL_BARS]
    orh = max(b["high"] for b in or_bars)
    orl = min(b["low"]  for b in or_bars)
    rng = orh - orl

    post_or = ny[ORL_BARS:]
    if not post_or:
        return Setup("P1 NY-ORL Break", "ARMED", None, orh, orl, None, None, None,
                     f"OR set [{orl:.2f}-{orh:.2f}] range {rng:.2f}, awaiting break")

    last = post_or[-1]
    body = abs(last["close"] - last["open"])
    body_min = 0.3 * atr

    # Long trigger
    if last["close"] > orh and body >= body_min:
        stop = orl - 0.10 * atr
        t1 = orh + 1 * rng
        t2 = orh + 2 * rng
        rr1 = (t1 - last["close"]) / (last["close"] - stop) if last["close"] > stop else None
        return Setup("P1 NY-ORL Break", "TRIGGERED", "LONG",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"5m close {last['close']:.2f} > ORH {orh:.2f}, body {body:.2f} >= {body_min:.2f}")

    # Short trigger
    if last["close"] < orl and body >= body_min:
        stop = orh + 0.10 * atr
        t1 = orl - 1 * rng
        t2 = orl - 2 * rng
        rr1 = (last["close"] - t1) / (stop - last["close"]) if stop > last["close"] else None
        return Setup("P1 NY-ORL Break", "TRIGGERED", "SHORT",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"5m close {last['close']:.2f} < ORL {orl:.2f}, body {body:.2f} >= {body_min:.2f}")

    # Still inside range
    return Setup("P1 NY-ORL Break", "ARMED", None, None,
                 round(orl, 2), round(orh, 2), None, None,
                 f"price {last['close']:.2f} inside OR [{orl:.2f}-{orh:.2f}]")


def detect_p2_failed_breakout(bars: list[dict], atr: float) -> Setup:
    if len(bars) < 10:
        return Setup("P2 Failed Breakout Fade", "DORMANT", None, None, None,
                     None, None, None, "<10 bars of history")

    # Reference = today excluding last 2 bars
    today_bars = [b for b in bars if _parse_ts(b["ts"]).date() == _parse_ts(bars[-1]["ts"]).date()]
    if len(today_bars) < 6:
        return Setup("P2 Failed Breakout Fade", "DORMANT", None, None, None,
                     None, None, None, "today session too thin")

    ref_window = today_bars[:-2]
    last2      = today_bars[-2:]
    ref_high   = max(b["high"] for b in ref_window)
    ref_low    = min(b["low"]  for b in ref_window)
    last       = bars[-1]

    # Upside failed breakout = last2 broke above ref_high, last bar closed back below
    last2_max = max(b["high"] for b in last2)
    if last2_max > ref_high and last["close"] < ref_high:
        stop = last2_max + 0.10 * atr
        t1 = ref_low
        t2 = today_bars[0]["open"]  # back to NY open
        rr1 = (last["close"] - t1) / (stop - last["close"]) if stop > last["close"] else None
        return Setup("P2 Failed Breakout Fade", "TRIGGERED", "SHORT",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"poked {last2_max:.2f} > ref_high {ref_high:.2f}, closed back at {last['close']:.2f}")

    # Mirror: failed breakdown = last2 broke below ref_low, last bar closed back above
    last2_min = min(b["low"] for b in last2)
    if last2_min < ref_low and last["close"] > ref_low:
        stop = last2_min - 0.10 * atr
        t1 = ref_high
        t2 = today_bars[0]["open"]
        rr1 = (t1 - last["close"]) / (last["close"] - stop) if last["close"] > stop else None
        return Setup("P2 Failed Breakout Fade", "TRIGGERED", "LONG",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"flushed {last2_min:.2f} < ref_low {ref_low:.2f}, reclaimed {last['close']:.2f}")

    return Setup("P2 Failed Breakout Fade", "DORMANT", None, None, None,
                 round(ref_low, 2), round(ref_high, 2), None,
                 f"in range; today ref [{ref_low:.2f}-{ref_high:.2f}]")


def detect_p3_trend_continuation(bars: list[dict], atr: float) -> Setup:
    if len(bars) < 8:
        return Setup("P3 Trend Continuation", "DORMANT", None, None, None,
                     None, None, None, "<8 bars of history")

    window = bars[-8:]
    highs = [b["high"] for b in window]
    lows  = [b["low"]  for b in window]
    closes = [b["close"] for b in window]

    # Heuristic: monotonic-ish higher closes
    higher = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
    lower  = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])

    last = bars[-1]
    # Require 6/7 directional closes (not 5) and ATR-scaled stop floor of 1.5×ATR
    if higher >= 6 and last["close"] > closes[0]:
        swing_low = min(lows[-3:]) if len(lows) >= 3 else lows[0]
        stop = min(swing_low - 0.10 * atr, last["close"] - 1.5 * atr)
        t1 = last["close"] + 2 * atr
        t2 = last["close"] + 4 * atr
        rr1 = (t1 - last["close"]) / (last["close"] - stop) if last["close"] > stop else None
        return Setup("P3 Trend Continuation", "TRIGGERED", "LONG",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"uptrend {higher}/7 up-closes; ATR-floored stop")

    if lower >= 6 and last["close"] < closes[0]:
        swing_high = max(highs[-3:]) if len(highs) >= 3 else highs[0]
        stop = max(swing_high + 0.10 * atr, last["close"] + 1.5 * atr)
        t1 = last["close"] - 2 * atr
        t2 = last["close"] - 4 * atr
        rr1 = (last["close"] - t1) / (stop - last["close"]) if stop > last["close"] else None
        return Setup("P3 Trend Continuation", "TRIGGERED", "SHORT",
                     round(last["close"], 2), round(stop, 2),
                     round(t1, 2), round(t2, 2),
                     round(rr1, 2) if rr1 else None,
                     f"downtrend {lower}/7 down-closes; ATR-floored stop")

    return Setup("P3 Trend Continuation", "DORMANT", None, None, None,
                 None, None, None,
                 f"chop: {higher} up / {lower} down closes in last 7 bars")


def detect_all(bars: list[dict]) -> dict[str, Any]:
    atr = _atr(bars, n=14)
    setups = [
        detect_p1_ny_orl_break(bars, atr),
        detect_p2_failed_breakout(bars, atr),
        detect_p3_trend_continuation(bars, atr),
    ]
    # Pick best triggered by rr1 if any
    triggered = [s for s in setups if s.state == "TRIGGERED"]
    best = max(triggered, key=lambda s: s.rr1 or 0) if triggered else None
    return {
        "atr_5m":    round(atr, 2),
        "setups":    [asdict(s) for s in setups],
        "primary":   asdict(best) if best else None,
        "any_triggered": bool(triggered),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bars", help="path to JSON file with bars list")
    p.add_argument("--symbol", default="GC=F")
    p.add_argument("--interval", default="5m")
    p.add_argument("--period", default="5d")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.bars:
        with open(args.bars) as f:
            bars = json.load(f)
    else:
        if not _HAS_YF:
            print("ERROR: yfinance not installed; pass --bars instead", file=sys.stderr)
            return 1
        # Inline fetch via fetch_tape helper
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
        from fetch_tape import fetch_intraday_bars
        bars = fetch_intraday_bars(args.symbol, args.interval, args.period)
        # filter to last 2 days to keep FSM relevant
        if bars:
            last_date = _parse_ts(bars[-1]["ts"]).date()
            bars = [b for b in bars
                    if (_parse_ts(b["ts"]).date() - last_date).days >= -1]

    if not bars:
        print("ERROR: no bars to analyze", file=sys.stderr)
        return 1

    result = detect_all(bars)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"ATR(5m, 14): {result['atr_5m']:.2f}")
    print()
    for s in result["setups"]:
        state = s["state"]
        marker = {"TRIGGERED": ">>", "ARMED": " ·", "DORMANT": "  ",
                  "INVALIDATED": "X "}[state]
        side = f" [{s['side']}]" if s['side'] else ""
        print(f"{marker} {s['name']:30s} {state}{side}")
        if state == "TRIGGERED":
            print(f"     entry {s['entry']:.2f}  stop {s['stop']:.2f}  "
                  f"T1 {s['target1']:.2f}  T2 {s['target2']:.2f}  rr1 {s['rr1']}")
        print(f"     {s['notes']}")
    print()
    if result["primary"]:
        p = result["primary"]
        print(f"PRIMARY SIGNAL: {p['name']} {p['side']}")
        print(f"   entry {p['entry']}  stop {p['stop']}  T1 {p['target1']}  T2 {p['target2']}  rr1 {p['rr1']}")
    else:
        print("PRIMARY SIGNAL: none (stand down)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
