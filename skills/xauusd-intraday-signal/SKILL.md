---
name: xauusd-intraday-signal
description: Generate an intraday BUY/SELL/STAND_DOWN signal for XAU/USD (gold) from live tape via yfinance, with event-driven blackouts, FSM-based setup detection, position sizing, and a one-page PDF signal card. Use when the user asks for a current gold trade signal, intraday gold posture, or to "check the tape" for gold.
---

# XAU/USD Intraday Signal

## Overview

End-to-end pipeline that fetches the live macro tape, applies an event-blackout filter, runs three intraday pattern detectors against 5-minute gold-futures bars, and emits a single decision: `BUY`, `SELL`, or `STAND_DOWN`. Output is a one-page vector PDF card and a JSON payload.

Designed for the solo trader who wants a single CLI call to ask "what should I do with gold right now?" without reading a page of analysis.

## When to Use

- User asks for an intraday XAU/USD or gold trading signal
- User wants to "check the tape" or "refresh the snapshot" for gold
- User wants a pre-event posture (e.g., before a CPI / NFP / FOMC release)
- User wants to know if gold is in setup mode, wait mode, or active trigger mode

Do **not** use this for:
- Multi-day swing positioning (use `scenario-analyzer` instead)
- Long-term gold thesis (use `market-environment-analysis` instead)
- Equity gold miners (GDX/GDXJ) — this is XAU spot/futures only

## Prerequisites

- Python 3.9+
- `yfinance` (free, no API key)
- `matplotlib` (for PDF card)
- Optional: `TWELVEDATA_API_KEY` env var → upgrades XAU/USD spot from gold-futures (GC=F) proxy to true spot

## Workflow

### Step 1: Run the orchestrator

```bash
python3 skills/xauusd-intraday-signal/scripts/generate_signal.py
```

Optional flags:
- `--account 100000` — account size for sizing (default 100000 USD)
- `--risk 0.5` — risk per trade in % (default 0.5)
- `--no-pdf` — skip PDF generation
- `--json` — emit machine-readable JSON
- `--output-dir reports/` — where to save PDF

### Step 2: Read the decision line

The orchestrator prints one of:

| Decision | Meaning | Action |
|---|---|---|
| `BUY` | Long setup triggered, event guard clear | Enter the long at displayed entry |
| `SELL` | Short setup triggered, event guard clear | Enter the short at displayed entry |
| `STAND_DOWN` | Either event blackout, wind-down, or no setup | Wait |

### Step 3: Open the PDF card

Saved to `reports/xauusd_signal_<YYYY-MM-DD_HHMM>.pdf`. The card contains:
- Decision badge (BUY/SELL/STAND_DOWN)
- Entry / stop / T1 / T2 / size if active
- Setup detector states (all 3 patterns)
- Live tape (XAU, DXY, US10Y, VIX, GVZ, WTI)
- Risk rules and timing line

## Architecture

```
generate_signal.py  (orchestrator)
        │
        ├──> fetch_tape.py        — yfinance (GC=F, DX-Y.NYB, ^TNX, ^VIX, ^GVZ, ^GSPC, CL=F)
        │                           Optional Twelve Data spot if TWELVEDATA_API_KEY set
        │
        ├──> event_guard.py       — tier-1/2 event blackout windows
        │                           ALLOWED / WIND_DOWN / BLOCKED
        │
        ├──> detect_setup.py      — 3 patterns evaluated on 5m GC=F bars:
        │                           P1 NY-ORL Break (long/short)
        │                           P2 Failed Breakout Fade (short/long)
        │                           P3 Trend Continuation (long/short)
        │                           Each: DORMANT / ARMED / TRIGGERED / INVALIDATED
        │
        ├──> [synthesize]         — decision tree:
        │                            BLOCKED       → STAND_DOWN
        │                            WIND_DOWN     → STAND_DOWN
        │                            no trigger    → STAND_DOWN
        │                            trigger + ok  → BUY/SELL
        │
        └──> render_signal_card.py — one-page vector PDF + PNG
```

## Output Format

### Stdout (human view)

```
======================================================================
 XAU/USD INTRADAY SIGNAL   |   WAIT
======================================================================
 no setup triggered
 as of 2026-05-12T11:26:20+00:00

 Event Guard:    ALLOWED
                 next: US April CPI in 63min

 Tape (GC=F):
   last      4703.50   chg -0.322
   range     4692.40 - 4739.60   open 4729.10
   DXY       98.29  (0.359%)
   VIX       18.90  (2.829%)
   WTI       101.35  (3.345%)

 no trade emitted
```

### PDF Card
- Letter portrait, single page
- Top: title bar + decision pill
- Mid-upper: big signal box (BUY/SELL/STAND_DOWN) with entry/stop/target grid
- Mid: setup detector status (3 patterns, color-coded dots)
- Mid-lower: live tape strip (6 instruments)
- Lower: risk rules + timing line
- Footer: data source attribution

### JSON payload
Full decision tree state, suitable for piping to other tools or storing as thesis. Includes:
- `decision`, `reason`, `as_of`
- `guard` — full event_guard state
- `tape` — full snapshot dict from fetch_tape
- `detection` — all 3 setups' states
- `trade` — full trade params if active

## Risk Rules (Baked In)

These appear on every signal card:

1. **Hard stop** — at the level shown; no averaging down
2. **Time stop** — close by next tier-1 event on calendar
3. **Daily DD** — −2R cumulative loss → power down for the day
4. **Late session** — no new entries after 15:30 ET
5. **Powell exit** — do not hold XAU into 2026-05-15

## Reference Documents

See `references/`:
- `intraday_setups.md` — the 3 patterns in detail with entry/stop/target rules
- `event_blackouts.md` — calendar event tiers and blackout windows
- `correlation_anchors.md` — XAU vs DXY/real-yield/oil for confluence
- `kill_switch_rules.md` — daily drawdown and circuit-breaker rules

## Upgrade Path

To get true XAU/USD spot (vs GC=F futures proxy with $1–3 spread):

1. Sign up at https://twelvedata.com (free, 60s, no card)
2. `export TWELVEDATA_API_KEY=your_key`
3. Re-run `generate_signal.py` — script auto-detects the key and uses Twelve Data for spot

To get broker-grade live streaming for production trading:
- Use OANDA practice account → real-time XAU_USD via REST/streaming, free demo tier
- Build a separate `fetch_tape_oanda.py` adapter and route in `generate_signal.py`

## Known Limitations

- GC=F gold futures has a $1–3 spread to XAU spot; for retail FX trading this matters
- yfinance 1m bars are limited to last ~7 days
- US yields (^TNX, ^TYX) and VIX cash do not always update in real-time intraday on yfinance
- Calendar in `event_guard.py` is hand-curated; update before each new month
- FSM state is computed fresh on every call (no persistence); not suitable for backtesting
