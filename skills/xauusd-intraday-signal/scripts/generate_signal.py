"""End-to-end intraday XAU/USD signal generator.

Pipeline:
    fetch_tape  ->  event_guard  ->  detect_setup  ->  render_signal_card

Decision logic:
    event_guard = BLOCKED    -> STAND_DOWN (no entries, blackout active)
    event_guard = WIND_DOWN  -> STAND_DOWN (event imminent, do not initiate)
    no setup triggered       -> STAND_DOWN (no edge right now)
    setup triggered          -> emit BUY/SELL with entry/stop/target + PDF

Usage:
    python generate_signal.py                    # full pipeline + PDF
    python generate_signal.py --no-pdf
    python generate_signal.py --account 100000 --risk 0.5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 stdout on Windows
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fetch_tape import fetch_tape, fetch_intraday_bars
from event_guard import evaluate as evaluate_guard
from detect_setup import detect_all


def compute_size(account: float, risk_pct: float, entry: float, stop: float
                 ) -> dict[str, float | int]:
    """Sizing helper - dollars-per-oz of XAU spot."""
    if entry == stop:
        return {"oz": 0, "notional": 0.0, "risk_dollars": 0.0}
    risk_per_oz = abs(entry - stop)
    dollar_risk = account * risk_pct / 100
    oz          = dollar_risk / risk_per_oz
    return {
        "oz":            round(oz, 2),
        "notional":      round(oz * entry, 0),
        "risk_dollars":  round(dollar_risk, 0),
        "risk_per_oz":   round(risk_per_oz, 2),
    }


def synthesize(tape: dict, guard: dict, detection: dict,
               account: float, risk_pct: float) -> dict[str, Any]:
    """Combine the three inputs into a single decision payload."""
    now = datetime.now(timezone.utc).isoformat()

    if guard["state"] == "BLOCKED":
        return {
            "decision":    "STAND_DOWN",
            "reason":      guard["reason"],
            "guard":       guard,
            "tape":        tape,
            "detection":   detection,
            "trade":       None,
            "as_of":       now,
        }

    if guard["state"] == "WIND_DOWN":
        return {
            "decision":    "STAND_DOWN",
            "reason":      f"wind-down: {guard['reason']}",
            "guard":       guard,
            "tape":        tape,
            "detection":   detection,
            "trade":       None,
            "as_of":       now,
        }

    primary = detection.get("primary")
    if not primary:
        return {
            "decision":    "STAND_DOWN",
            "reason":      "no setup triggered",
            "guard":       guard,
            "tape":        tape,
            "detection":   detection,
            "trade":       None,
            "as_of":       now,
        }

    # ALLOWED + triggered -> emit trade
    side = primary["side"]
    entry, stop = primary["entry"], primary["stop"]
    sizing = compute_size(account, risk_pct, entry, stop)

    return {
        "decision":    "BUY" if side == "LONG" else "SELL",
        "reason":      f"{primary['name']} {side} triggered; rr1 {primary['rr1']}",
        "guard":       guard,
        "tape":        tape,
        "detection":   detection,
        "trade": {
            "side":        side,
            "entry":       entry,
            "stop":        stop,
            "target1":     primary["target1"],
            "target2":     primary["target2"],
            "rr1":         primary["rr1"],
            "sizing":      sizing,
            "setup":       primary["name"],
            "notes":       primary["notes"],
        },
        "as_of":       now,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--account", type=float, default=100_000,
                   help="account size in USD (default 100000)")
    p.add_argument("--risk", type=float, default=0.5,
                   help="risk percent per trade (default 0.5)")
    p.add_argument("--no-pdf",  action="store_true")
    p.add_argument("--output-dir", default="reports")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    # 1. Tape
    tape = fetch_tape(interval="5m", period="5d")

    # 2. Guard
    guard_state = evaluate_guard()
    guard = {
        "state":               guard_state.state,
        "reason":              guard_state.reason,
        "next_event":          guard_state.next_event,
        "next_event_ts":       guard_state.next_event_ts,
        "minutes_to_next":     guard_state.minutes_to_next,
        "minutes_in_blackout": guard_state.minutes_in_blackout,
    }

    # 3. Detection
    bars = fetch_intraday_bars("GC=F", "5m", "5d")
    # Trim to last 1.5 days for FSM relevance
    if bars:
        from datetime import datetime as _dt
        last_d = _dt.fromisoformat(bars[-1]["ts"]).date()
        bars = [b for b in bars
                if (_dt.fromisoformat(b["ts"]).date() - last_d).days >= -1]
    detection = detect_all(bars)

    # 4. Synthesize
    signal = synthesize(tape, guard, detection, args.account, args.risk)

    # 5. Output JSON optionally
    if args.json:
        print(json.dumps(signal, indent=2, default=str))
    else:
        _print_human(signal)

    # 6. PDF
    if not args.no_pdf:
        try:
            from render_signal_card import render
            outdir = Path(args.output_dir)
            outdir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
            pdf_path = outdir / f"xauusd_signal_{stamp}.pdf"
            render(signal, pdf_path)
            print(f"\nPDF: {pdf_path.resolve()}")
        except Exception as e:
            print(f"\n[!] PDF render failed: {e}", file=sys.stderr)

    return 0


def _print_human(s: dict) -> None:
    decision = s["decision"]
    marker   = {"BUY": "BUY ", "SELL": "SELL", "STAND_DOWN": "WAIT"}[decision]
    print("=" * 70)
    print(f" XAU/USD INTRADAY SIGNAL   |   {marker}")
    print("=" * 70)
    print(f" {s['reason']}")
    print(f" as of {s['as_of']}")
    print()

    g = s["guard"]
    print(f" Event Guard:    {g['state']}")
    if g["next_event"]:
        print(f"                 next: {g['next_event']} in {g['minutes_to_next']}min")
    print()

    tickers = s["tape"]["tickers"]
    gold = tickers.get("xauusd_spot") or tickers.get("gold", {})
    if gold:
        sym = gold.get("symbol", "GC=F")
        print(f" Tape ({sym}):")
        print(f"   last      {gold['last']:.2f}   "
              f"chg {gold.get('change_pct', 'n/a')}")
        print(f"   range     {gold['day_low']:.2f} - {gold['day_high']:.2f}   "
              f"open {gold['day_open']:.2f}")
    if "dxy" in tickers:
        print(f"   DXY       {tickers['dxy']['last']:.2f}  "
              f"({tickers['dxy'].get('change_pct', '?')}%)")
    if "vix" in tickers:
        print(f"   VIX       {tickers['vix']['last']:.2f}  "
              f"({tickers['vix'].get('change_pct', '?')}%)")
    if "wti" in tickers:
        print(f"   WTI       {tickers['wti']['last']:.2f}  "
              f"({tickers['wti'].get('change_pct', '?')}%)")
    print()

    if s["trade"]:
        t = s["trade"]
        sz = t["sizing"]
        print(f" TRADE   {t['side']}   ({t['setup']})")
        print(f"   entry    {t['entry']:.2f}")
        print(f"   stop     {t['stop']:.2f}   risk/oz {sz['risk_per_oz']:.2f}")
        print(f"   T1       {t['target1']:.2f}")
        print(f"   T2       {t['target2']:.2f}")
        print(f"   rr1      {t['rr1']}")
        print(f"   sizing   {sz['oz']} oz   notional ${sz['notional']:,.0f}   "
              f"risk ${sz['risk_dollars']:,.0f}")
        print(f"   {t['notes']}")
    else:
        print(" no trade emitted")
    print()


if __name__ == "__main__":
    sys.exit(main())
