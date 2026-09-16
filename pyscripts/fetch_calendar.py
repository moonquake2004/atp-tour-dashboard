#!/usr/bin/env python3
"""
Fetch the ATP tour calendar.

One page lists the whole season: every tournament with its date, surface, prize
money, draw size and singles champion, including events that have not been played
yet.  That makes it the authoritative calendar — the day-by-day results crawl can
only see tournaments that already have results.

    python3 pyscripts/fetch_calendar.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import te
from wtalib import log, write_json

LEVEL_FROM_TYPE = {"main": "ATP Tour", "lower": "Challenger", "exhibitions": "Exhibition"}

SLAM_SLUGS = {"australian-open", "french-open", "wimbledon", "us-open"}


def main() -> int:
    log("calendar", "Fetching the ATP tour calendar…")

    events = te.parse_calendar(te.get(te.CALENDAR_BASE))
    if not events:
        raise SystemExit("calendar page returned no events")

    for event in events:
        slug = event["path"].strip("/").split("/")[0]
        if slug in SLAM_SLUGS:
            event["level"] = "Grand Slam"
        elif slug in ("masters-cup", "atp-finals", "next-gen-finals"):
            event["level"] = "Tour Finals"
        elif slug.startswith(("davis-cup", "united-cup", "atp-cup")):
            event["level"] = "Team Cup"
        else:
            event["level"] = LEVEL_FROM_TYPE.get(event["type"], "ATP Tour")
        event["slug"] = slug

    # One entry per tournament-season, newest first.
    by_path: dict[str, dict] = {}
    for event in events:
        by_path.setdefault(event["path"], event)

    write_json("data/calendar.json", {
        "source": "Tennis Explorer (ATP tour calendar)",
        "sourceUrl": te.BASE + te.CALENDAR_BASE,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "events": sorted(by_path.values(), key=lambda e: (e["date"], e["name"])),
    })

    played = sum(1 for e in by_path.values() if e["played"])
    upcoming = len(by_path) - played
    by_level: dict[str, int] = {}
    for event in by_path.values():
        by_level[event["level"]] = by_level.get(event["level"], 0) + 1
    log("calendar", f"Done — {len(by_path)} events ({played} played, {upcoming} scheduled) {by_level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
