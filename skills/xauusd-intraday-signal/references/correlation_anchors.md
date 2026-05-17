# Correlation Anchors for XAU/USD Intraday Confluence

The signal card displays a 6-instrument tape. Use these as confluence reads when deciding whether to act on a triggered setup, scale up, or stand aside.

## Primary anchors

### DXY (dollar index)
- **Inverse to XAU** in normal regime (correlation rolls −0.5 to −0.8)
- Rising DXY intraday is a headwind for long-gold triggers
- Falling DXY intraday is a tailwind for long-gold triggers
- **Inflection threshold:** intraday change > ±0.4% is meaningful; below that is noise
- **Decision rule:** if a long XAU setup triggers while DXY is up >0.5% on the day, downgrade conviction by one level (rr1 must be > 2.0 to act)

### US 10Y nominal yield (^TNX)
- Less reliable intraday than DXY (yfinance feed is daily-stale)
- Use for regime context: rising yields generally compress gold long-side conviction
- **Inflection threshold:** day-over-day move of +5 bps or more is regime-relevant

### US 10Y TIPS real yield
- True gold headwind/tailwind anchor
- Not on yfinance; pull from FRED `DFII10` once per day for context, treat as a slow-moving regime variable
- **Stagflation override:** when CPI is hot and real yields are rising, the textbook "real-yield up = gold down" relationship CAN INVERT. Gold rallies on confirmed-stagflation print. The signal logic does not auto-detect this; flag manually if CPI surprises hot and gold doesn't drop.

## Geo / risk anchors

### WTI crude (CL=F)
- Proxy for geopolitical risk premium
- Rising WTI on Iran / Hormuz / OPEC headlines = gold haven bid tailwind
- **Inflection threshold:** intraday move >2% with sustained price (not a wick)
- **Decision rule:** if WTI is up >3% intraday, raise stop-loss tolerance on long XAU by 0.25 × ATR — the haven bid will absorb chop better than usual

### VIX
- Equity vol; rising VIX often coincides with gold bid (haven flow)
- Caveat: VIX intraday updates on yfinance are slow; check at 30-min granularity
- **Inflection threshold:** VIX above 22 = regime stress, gold long-side asymmetry improves

### GVZ (gold ETF vol index)
- Direct gold IV gauge
- Normal range: 12–18
- Elevated: 18–25
- Stress: 25+
- **Decision rule:** when GVZ > 25, all setups should require rr1 > 2.5 to act (you are paying high vol; need bigger payoff)

## Pre-event behavior

Confluence reads degrade rapidly inside event blackouts. Correlations between gold and DXY can momentarily invert as algorithmic hedging adjusts ahead of the print. Treat the tape as informational, not actionable, in the T−30min window.

## Stagflation regime flag (important)

If TWO of the following are true, suspend the "real-yield up = gold down" mechanical trade and use only setup signals on their own merit:
1. Last CPI print > consensus by ≥ 0.1% on core
2. WTI > $90 with rising oil-vol (OVX > 35)
3. Fed pricing shows hike probability rising (i.e. yields up + DXY up + gold up simultaneously, against textbook)

When in stagflation regime, XAU's effective beta to DXY drops to −0.2 (from typical −0.6) and gold trades as a regime-uncertainty hedge, not a real-yield instrument.
