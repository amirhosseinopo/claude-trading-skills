# Kill-Switch Rules

These rules are non-negotiable for the intraday XAU/USD signal user. They appear on every signal card as Risk Rules but are documented here for the reasoning.

## 1. Hard stop, no average-down

Every signal includes an explicit stop. The trader closes the position when price hits the stop, full size, no exceptions. Averaging down doubles exposure precisely when the thesis is being invalidated by price action — the worst possible cost-benefit ratio.

**Operational rule:** place a hard stop-loss order at the broker the moment the entry fills. Do not use mental stops.

## 2. Time stop = next tier-1 event

If T1 has not been reached by the time the next tier-1 event on the calendar is within blackout range, close the position. Rationale: the setup that triggered the entry was a function of the regime at that moment; the regime may shift over the print. Better to take small P&L and re-engage post-event than to ride a stale thesis through a 5× spread widening.

## 3. Daily drawdown circuit = −2R

If cumulative realized losses for the day reach 2 × the per-trade dollar risk (e.g. $1,000 on a $100k account at 0.5% risk), stop trading XAU for the day. No exceptions.

Why: two losses in a row from the same signal source signals that the current regime is not the one the patterns were calibrated for. Continuing to trade is paying tuition to learn this. Better to stop, journal, and re-evaluate the next session.

## 4. Consecutive loss circuit = 3 in a row

If you take 3 consecutive losing trades on this signal source, regardless of total P&L, stop for the day. Same regime-mismatch logic as #3.

## 5. No new entries after 15:30 ET

The last 30 minutes of the NY cash session has the worst intraday signal-to-noise ratio:
- Position-squaring flows distort price
- Spreads widen ahead of the close
- Targets are unlikely to be hit before time stop

Exit any held positions or convert to a swing decision (which is OUTSIDE the scope of this skill).

## 6. Powell exit blackout: no XAU positions held into 2026-05-15

The Powell chair-term expiry on 2026-05-15 creates an unbounded regime-uncertainty risk that no intraday setup can price. Close all XAU positions by 15:30 ET on Thursday 2026-05-14 at the latest.

## 7. Spread filter

If at the moment of entry your broker shows XAU/USD spread > 0.7 pips (retail) or > 0.4 pips (institutional), pass on the trade. The spread will eat your edge on tight stops. This rule does not appear on the card because it is broker-specific; check yours.

## 8. Sizing sanity check

The orchestrator computes oz, notional, and dollar risk. Before clicking buy:
- Notional should not exceed 100% of account equity (for cash trading) or your margin allowance (for futures/CFD)
- If notional > 50% of account on a single position, downsize regardless of risk budget — concentration risk overrides position-sizing math

## 9. News override

If a tier-1 geopolitical headline drops while you have an active position (e.g. Hormuz formal closure, Trump-Iran ceasefire breakthrough, US service member casualty), close the position immediately at market regardless of P&L. The setup that triggered your entry no longer applies.

## 10. Journal every trade

After each completed trade (win or loss):
- What pattern triggered
- What the tape looked like (DXY/WTI/VIX direction)
- Why you took it
- What the actual exit was
- One lesson

Use `trader-memory-core` for this; see CLAUDE.md for the SOP.
