"""Event guard for intraday XAU/USD signal generation.

Tier-1 events get a blackout window (default T-30 to T+30 min) during which
no new entries are emitted. This is the single biggest "edge" over a desktop
trader who clicks buy 90 seconds before CPI.

Calendar is a hand-curated list; update as new events are scheduled. For a
fully automated calendar source, point this at FMP or investing.com later.

Usage:
    python event_guard.py                       # show current state
    python event_guard.py --now 2026-05-12T12:25:00Z
    python event_guard.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


# Hand-curated tier-1 events. ISO 8601 UTC.
# Add as needed; this is the v1 seed.
EVENTS: list[dict[str, str | int]] = [
    # US April CPI release 2026-05-12 08:30 ET = 12:30 UTC
    {"name": "US April CPI",            "ts": "2026-05-12T12:30:00Z", "tier": 1, "category": "data"},
    {"name": "US April PPI",            "ts": "2026-05-13T12:30:00Z", "tier": 1, "category": "data"},
    {"name": "US Initial Jobless Claims","ts": "2026-05-14T12:30:00Z", "tier": 2, "category": "data"},
    {"name": "Powell Fed Chair Term End","ts": "2026-05-15T20:00:00Z", "tier": 1, "category": "fed"},
    # NFP - first Friday of next month
    {"name": "US May NFP",              "ts": "2026-06-05T12:30:00Z", "tier": 1, "category": "data"},
    # FOMC June 2026
    {"name": "FOMC Decision",           "ts": "2026-06-17T18:00:00Z", "tier": 1, "category": "fed"},
    {"name": "FOMC Powell Press Conf",  "ts": "2026-06-17T18:30:00Z", "tier": 1, "category": "fed"},
]

# Blackout windows by tier (minutes before, minutes after)
BLACKOUT_WINDOWS = {
    1: (30, 30),   # tier 1: CPI, NFP, FOMC — 60-min total blackout
    2: (15, 15),   # tier 2: claims, secondary data — 30-min blackout
}


@dataclass
class GuardState:
    state: str               # ALLOWED | BLOCKED | WIND_DOWN
    reason: str
    next_event: str | None
    next_event_ts: str | None
    minutes_to_next: int | None
    minutes_in_blackout: int | None


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def evaluate(now: datetime | None = None,
             events: list[dict] | None = None) -> GuardState:
    """Decide whether new entries are allowed at `now`."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    events = events if events is not None else EVENTS

    upcoming = []
    for ev in events:
        ts = _parse_iso(str(ev["ts"]))
        tier = int(ev["tier"])
        before_min, after_min = BLACKOUT_WINDOWS.get(tier, (10, 10))

        # In blackout window?
        if ts - timedelta(minutes=before_min) <= now <= ts + timedelta(minutes=after_min):
            mins_in = int((now - (ts - timedelta(minutes=before_min))).total_seconds() / 60)
            return GuardState(
                state               = "BLOCKED",
                reason              = f"tier-{tier} event blackout: {ev['name']}",
                next_event          = str(ev["name"]),
                next_event_ts       = ev["ts"],
                minutes_to_next     = int((ts - now).total_seconds() / 60),
                minutes_in_blackout = mins_in,
            )
        if ts > now:
            upcoming.append((ts, ev, before_min, after_min))

    upcoming.sort(key=lambda x: x[0])
    if not upcoming:
        return GuardState(
            state="ALLOWED", reason="no upcoming tier-1/2 events on calendar",
            next_event=None, next_event_ts=None,
            minutes_to_next=None, minutes_in_blackout=None,
        )

    ts, ev, before_min, after_min = upcoming[0]
    minutes_to = int((ts - now).total_seconds() / 60)

    # WIND_DOWN: within 2× blackout window pre-event = don't open new trades
    # (close-existing logic is up to the trader, but we don't initiate)
    if minutes_to <= before_min * 2:
        return GuardState(
            state               = "WIND_DOWN",
            reason              = f"{minutes_to}min to {ev['name']} (tier {ev['tier']}) — no new entries",
            next_event          = str(ev["name"]),
            next_event_ts       = ts.isoformat(),
            minutes_to_next     = minutes_to,
            minutes_in_blackout = None,
        )

    return GuardState(
        state               = "ALLOWED",
        reason              = f"clear; next event {ev['name']} in {minutes_to}min",
        next_event          = str(ev["name"]),
        next_event_ts       = ts.isoformat(),
        minutes_to_next     = minutes_to,
        minutes_in_blackout = None,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--now", help="ISO UTC override (e.g. 2026-05-12T12:25:00Z)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    now = _parse_iso(args.now) if args.now else None
    g = evaluate(now)

    if args.json:
        print(json.dumps(asdict(g), indent=2))
        return 0

    color = {"ALLOWED": "OK", "WIND_DOWN": "!", "BLOCKED": "X"}[g.state]
    print(f"[{color}] {g.state}")
    print(f"     reason: {g.reason}")
    if g.next_event:
        print(f"     next:   {g.next_event} at {g.next_event_ts}")
        if g.minutes_to_next is not None:
            print(f"     T-:     {g.minutes_to_next}min")
        if g.minutes_in_blackout is not None:
            print(f"     in BO:  {g.minutes_in_blackout}min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
