"""Render the intraday XAU/USD signal as a one-page PDF card.

Takes the dict produced by generate_signal.synthesize() and emits a vector PDF.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch
import matplotlib as mpl

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# palette
INK, PAPER     = "#0b1220", "#ffffff"
SOFT, RULE     = "#f5f6f8", "#d6dae0"
SUBTLE         = "#6b7280"
BULL, BULL_BG  = "#0f8a5f", "#e6f3ec"
BEAR, BEAR_BG  = "#c41e3a", "#fce6ea"
WARN, WARN_BG  = "#b45309", "#fdf2d6"
NEUT, NEUT_BG  = "#4b5563", "#eceef1"


mpl.rcParams["font.family"] = "DejaVu Sans"
mpl.rcParams["pdf.fonttype"] = 42


def render(signal: dict, out_path: Path) -> None:
    decision = signal["decision"]
    is_buy   = decision == "BUY"
    is_sell  = decision == "SELL"
    is_wait  = decision == "STAND_DOWN"

    if is_buy:
        side_color, side_bg, arrow, label = BULL, BULL_BG, "UP", "BUY  XAU/USD"
    elif is_sell:
        side_color, side_bg, arrow, label = BEAR, BEAR_BG, "DOWN", "SELL  XAU/USD"
    else:
        side_color, side_bg, arrow, label = NEUT, NEUT_BG, "WAIT", "STAND  DOWN"

    fig = plt.figure(figsize=(8.5, 11.0), dpi=200)
    ax  = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 8.5); ax.set_ylim(0, 11)
    ax.set_axis_off(); ax.set_facecolor(PAPER)

    def box(x, y, w, h, fc=PAPER, ec=RULE, lw=0.8, r=0.10, z=1):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
            boxstyle=f"round,pad=0,rounding_size={r}",
            fc=fc, ec=ec, lw=lw, zorder=z))

    def t(x, y, s, size=10, color=INK, weight="normal", ha="left", va="baseline",
          mono=False, z=5, style="normal"):
        kw = dict(fontsize=size, color=color, ha=ha, va=va, weight=weight,
                  zorder=z, style=style)
        if mono: kw["family"] = "DejaVu Sans Mono"
        ax.text(x, y, s, **kw)

    def pill(cx, cy, w, h, lab, fg, bg, size=8):
        box(cx, cy, w, h, fc=bg, ec=bg, r=0.10, z=8)
        t(cx + w/2, cy + h/2, lab, size=size, color=fg, weight="bold",
          ha="center", va="center", z=9)

    # ====================== HEADER
    box(0.5, 9.7, 7.5, 0.85, fc=INK, ec=INK, r=0.08)
    t(0.75, 10.20, "XAU/USD  ·  INTRADAY  SIGNAL", size=20, color=PAPER,
      weight="bold", va="center")
    t(0.75, 9.90, signal["as_of"].split("T")[0] + "  ·  " +
      signal["as_of"].split("T")[1][:5] + " UTC  ·  auto-generated",
      size=9, color="#c4cad6", va="center")
    # decision pill top right
    pill(6.20, 9.85, 1.65, 0.55, decision.replace("_", " "),
         INK if is_wait else "#0b1220",
         "#f0c674" if is_wait else side_bg, size=12)

    # ====================== BIG SIGNAL BOX
    box(0.5, 6.6, 7.5, 2.8, fc=side_bg, ec=side_color, lw=2.5, r=0.12)

    # left arrow / symbol
    t(1.6, 7.95, arrow, size=44, color=side_color, weight="bold",
      ha="center", va="center")

    # right text
    t(3.2, 8.80, label, size=32, color=side_color, weight="bold", va="center")
    t(3.2, 8.40, signal["reason"], size=10, color=INK, va="center")

    # data grid (or stand-down explanation)
    grid_y = 7.85
    if signal["trade"]:
        tr = signal["trade"]
        sz = tr["sizing"]
        rows = [
            ("ENTRY",   f"{tr['entry']:.2f}",        f"({tr['side'].lower()})"),
            ("STOP",    f"{tr['stop']:.2f}",         f"risk/oz ${sz['risk_per_oz']:.2f}"),
            ("T1 / T2", f"{tr['target1']:.2f} / {tr['target2']:.2f}",
                                                     f"rr1 = {tr['rr1']}"),
            ("SIZE",    f"{sz['oz']} oz",            f"notional ${sz['notional']:,.0f}  ·  risk ${sz['risk_dollars']:,.0f}"),
        ]
        for i, (k, v, note) in enumerate(rows):
            yy = grid_y - i * 0.30
            t(3.2,  yy, k,    size=8.5, color=SUBTLE, weight="bold", va="center")
            t(3.95, yy, v,    size=13,  color=INK, weight="bold", mono=True, va="center")
            t(5.30, yy, note, size=9,   color=SUBTLE, va="center")
    else:
        # stand-down narrative
        g = signal["guard"]
        t(3.2, 7.85, "Why no trade right now:", size=10, color=INK, weight="bold")
        lines = [
            f"  Guard state:   {g['state']}",
            f"  Next event:    {g['next_event'] or '—'}" +
                (f"  in {g['minutes_to_next']}min" if g['minutes_to_next'] else ""),
            f"  Setups:        {signal['detection'].get('any_triggered', False) and 'one triggered' or 'all dormant/armed'}",
        ]
        for i, ln in enumerate(lines):
            t(3.2, 7.55 - i * 0.25, ln, size=9.5, color=INK, mono=True)

    # ====================== SETUP DETAIL (always rendered)
    box(0.5, 5.10, 7.5, 1.35, fc=PAPER, ec=RULE)
    t(0.75, 6.30, "SETUP  DETECTOR", size=10, color=INK, weight="bold", va="center")

    setups = signal["detection"]["setups"]
    for i, s in enumerate(setups):
        yy = 5.95 - i * 0.32
        state = s["state"]
        c = {"TRIGGERED": BULL if s["side"] == "LONG" else BEAR,
             "ARMED":     WARN,
             "DORMANT":   SUBTLE,
             "INVALIDATED": BEAR}[state]
        # dot + text
        ax.add_patch(mp.Circle((0.85, yy), 0.06, fc=c, ec=c, zorder=4))
        t(0.98, yy + 0.04, s["name"], size=9, color=INK, weight="bold")
        suffix = f"  [{s['side']}]" if s["side"] else ""
        t(0.98, yy - 0.10, f"{state}{suffix}  ·  {s['notes']}", size=7.5,
          color=SUBTLE)

    # ====================== TAPE
    box(0.5, 3.40, 7.5, 1.55, fc=SOFT, ec=RULE)
    t(0.75, 4.80, "LIVE  TAPE", size=10, color=INK, weight="bold", va="center")

    tickers = signal["tape"]["tickers"]
    tape_rows = [
        ("XAU/USD", tickers.get("xauusd_spot") or tickers.get("gold", {})),
        ("DXY",     tickers.get("dxy", {})),
        ("US 10Y",  tickers.get("us10y", {})),
        ("VIX",     tickers.get("vix", {})),
        ("GVZ",     tickers.get("gvz", {})),
        ("WTI",     tickers.get("wti", {})),
    ]
    col_w = (7.5 - 0.5) / 6
    for i, (lab, snap) in enumerate(tape_rows):
        cx = 0.75 + i * col_w
        if not snap:
            continue
        t(cx + col_w/2, 4.45, lab, size=7.5, color=SUBTLE, weight="bold",
          ha="center", va="center")
        t(cx + col_w/2, 4.15, f"{snap.get('last', 0):.2f}",
          size=12, color=INK, weight="bold", mono=True,
          ha="center", va="center")
        chg = snap.get("change_pct")
        if chg is not None:
            chg_color = BULL if chg > 0 else BEAR if chg < 0 else SUBTLE
            sign = "+" if chg > 0 else ""
            t(cx + col_w/2, 3.85, f"{sign}{chg:.2f}%", size=7.5,
              color=chg_color, ha="center", va="center")

    # ====================== KILL SWITCH / EXIT RULES
    box(0.5, 1.95, 7.5, 1.30, fc="#fff5f4", ec=BEAR, lw=1.2)
    t(0.75, 3.10, "RISK  RULES", size=10, color=BEAR, weight="bold", va="center")

    rules = [
        ("Stop",          "hard stop at level shown above; no average-down"),
        ("Time stop",     "close by next tier-1 event (see header)"),
        ("Daily DD",      "-2R cumulative = power down for the day"),
        ("Late session",  "no new entries after 15:30 ET"),
        ("Powell exit",   "do not hold any XAU position into 2026-05-15"),
    ]
    for i, (k, v) in enumerate(rules):
        yy = 2.80 - i * 0.18
        t(0.85, yy, k, size=8.5, color=BEAR, weight="bold", va="center")
        t(1.85, yy, v, size=8.5, color=INK, va="center")

    # ====================== TIMING / FOOTER
    box(0.5, 0.95, 7.5, 0.85, fc=PAPER, ec=RULE)
    t(0.75, 1.55, "TIMING", size=9, color=SUBTLE, weight="bold", va="center")
    t(1.35, 1.55, _timing_line(signal), size=10, color=INK, va="center")
    t(0.75, 1.20, "DATA",   size=9, color=SUBTLE, weight="bold", va="center")
    t(1.35, 1.20, _data_line(signal), size=9, color=SUBTLE, va="center")

    t(0.5, 0.50, "Signal source: claude-trading-skills/xauusd-intraday-signal  ·  "
                 "data via yfinance + optional Twelve Data  ·  not investment advice",
      size=7, color=SUBTLE)

    fig.savefig(out_path, format="pdf")
    fig.savefig(out_path.with_suffix(".png"), format="png", dpi=170)
    plt.close(fig)


def _timing_line(s: dict) -> str:
    g = s["guard"]
    if g["state"] == "BLOCKED":
        return f"BLACKOUT — re-check after {g['next_event']} clears"
    if g["state"] == "WIND_DOWN":
        return f"WIND-DOWN — {g['minutes_to_next']}min to {g['next_event']}"
    if s["trade"]:
        return f"Active signal — re-check before {g['next_event'] or 'next event'}"
    return "Clear, no setup — re-check in 15min"


def _data_line(s: dict) -> str:
    td = s["tape"].get("td_used", False)
    src = "Twelve Data spot + yfinance macro" if td else "yfinance GC=F + macro (no spot key)"
    return src


if __name__ == "__main__":
    # Standalone test: read signal from stdin or a file path
    import json
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            sig = json.load(f)
    else:
        sig = json.load(sys.stdin)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("reports/_signal_test.pdf")
    render(sig, out)
    print(f"Wrote {out}")
