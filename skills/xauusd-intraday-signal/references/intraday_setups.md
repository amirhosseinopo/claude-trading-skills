# Intraday XAU/USD Setups

Three patterns evaluated on 5-min GC=F bars. Each can emit DORMANT / ARMED / TRIGGERED / INVALIDATED.

## P1: NY Opening Range Break (long or short)

**Premise.** Gold's most directional moves of the US session start when the NY-cash market opens and rebalances overnight Asian and London flows. The first 30 minutes (13:30–14:00 UTC) define the day's opening range. A clean break of that range with body conviction tends to extend.

**Setup parameters:**
- Opening range = first 6 bars (30 min) of NY session
- Long trigger: 5m close > ORH **AND** bar body ≥ 0.3 × ATR(14)
- Short trigger: 5m close < ORL **AND** bar body ≥ 0.3 × ATR(14)
- Stop:
  - Long: ORL − 0.1 × ATR
  - Short: ORH + 0.1 × ATR
- Targets:
  - T1: 1 × OR width beyond break level
  - T2: 2 × OR width

**When it fails.**
- Range bound day (NFP-week Mondays often chop)
- Pre-event days (CPI / FOMC mornings) — range gets distorted; use event_guard
- Low OR width (< 0.5 × ATR) → noise, skip

## P2: Failed Breakout Fade (short or long)

**Premise.** When price pokes above a fresh intraday high then closes back inside the prior range within 1–2 bars, it signals trapped longs. The reverse is true for failed breakdowns. The fade is highest-conviction when paired with macro confluence (DXY firm + failed gold break-up = strong fade).

**Setup parameters:**
- Reference window = today's bars except the last 2
- Reference high = max(high) of reference window
- Reference low  = min(low)  of reference window
- Short trigger: max(last 2 bars' high) > ref_high **AND** last bar's close < ref_high
- Long trigger:  min(last 2 bars' low)  < ref_low  **AND** last bar's close > ref_low
- Stop:
  - Short: last 2 bars' max + 0.1 × ATR
  - Long:  last 2 bars' min − 0.1 × ATR
- Targets:
  - T1: reference low (short) / reference high (long)
  - T2: NY session open

**When it fails.**
- News-driven spike that reverses on a single bar — wait for confirmation
- Volume-less afternoon poke — needs increasing volume on the rejection

## P3: Trend Continuation (long or short)

**Premise.** Once 6 of the last 7 closes are directional, momentum is dominant. Pullbacks to recent swing levels tend to resolve in the trend's direction with high hit rate.

**Setup parameters:**
- Look at last 8 bars (close-to-close)
- Long: 6+ up-closes out of 7 transitions AND last close > first close of window
- Short: 6+ down-closes out of 7 transitions AND last close < first close
- Stop:
  - Long: min( swing_low_last_3 − 0.1 × ATR, last_close − 1.5 × ATR )
  - Short: max( swing_high_last_3 + 0.1 × ATR, last_close + 1.5 × ATR )
- Targets:
  - T1: last_close + 2 × ATR (long) / − 2 × ATR (short)
  - T2: last_close + 4 × ATR (long) / − 4 × ATR (short)

**When it fails.**
- Range-break day: trend signal fires repeatedly but R:R is poor
- Pre-event compression: 6/7 up-closes can be artificial as price drifts on low volume

## Selection logic when multiple trigger

When more than one pattern triggers in the same bar, the orchestrator picks the one with the highest rr1 (T1 reward divided by stop distance). Ties prefer P1 > P2 > P3.

## ATR baseline

ATR(14) is computed on the same 5m bars. Typical ranges for GC=F at this price regime (~$4,700):
- Quiet session: 3–5 USD/oz
- Average: 5–7
- Pre-event spike or post-event: 10–20

If ATR > 12, treat all triggers with skepticism — high vol post-event often head-fakes.
