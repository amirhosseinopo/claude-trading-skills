# Event Blackout Rules

Hard rule: do not initiate intraday XAU/USD trades inside an event blackout window.

## Tier definitions

| Tier | Examples | Blackout window |
|---|---|---|
| 1 | US CPI, US PPI (M/M and Y/Y headlines), NFP, FOMC decision, FOMC press conf, Fed chair speech, ECB rate decision, US GDP advance | T−30min to T+30min |
| 2 | US initial jobless claims, US retail sales, US PCE deflator, US durable goods, ISM manufacturing/services | T−15min to T+15min |
| 3 | Regional Fed surveys, consumer confidence, housing starts | no blackout (information only) |

## Wind-down semantics

The orchestrator considers itself in `WIND_DOWN` when within **2 × blackout** pre-event. For tier-1 events that means T−60min, for tier-2 T−30min.

In `WIND_DOWN`:
- No new entries
- Existing positions: trader's call (this skill does not manage exits on open trades)

## Why blackouts matter

- Spread widens 5–10× across the print (retail spreads can go from 0.3 pip to 3+ pip)
- Stop-runs are routine — algorithmic hunters scan known stop clusters around the print
- Vol explodes then collapses; risk:reward of "guessing the direction" is asymmetric to the downside
- Hit rate on directional pre-event entries is statistically worse than waiting 5 minutes post-print

## Calendar maintenance

`event_guard.py` ships with a hand-curated `EVENTS` list. Update it:
- Monthly: pull the NFP and CPI dates for the following month
- Quarterly: refresh FOMC meeting dates
- Ad-hoc: add Fed-chair speeches, geopolitical event announcements

For full automation, replace the static list with a fetch from the FMP economic-calendar endpoint or investing.com RSS.

## Special: Powell transition (May 15 2026 only)

The 2026-05-15 entry treats the Powell chair-term expiry as tier-1. Even outside the +/-30min window, no XAU positions should be **held** into the transition because the new chair's first words become a regime-defining catalyst. This is enforced as a Risk Rule on the signal card, not a guard state.
