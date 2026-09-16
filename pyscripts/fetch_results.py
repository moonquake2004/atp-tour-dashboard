#!/usr/bin/env python3
"""
Crawl the tour day by day to build the calendar and the season results.

Tennis Explorer publishes, per day, every completed match across every tournament
in play, grouped under a heading that carries the event name, its country flag,
its surface and a link to the event's draw page.  Walking the days therefore
yields both the calendar and a complete result set — including the qualifying and
lower-tier events that no ranked player's own log would reveal.

    python3 pyscripts/fetch_results.py
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

import te
from wtalib import env_int, log, read_json, write_json

SEASONS = env_int("ATP_RESULT_SEASONS", 2)
SEASON = env_int("ATP_SEASON", datetime.now(timezone.utc).year)
TODAY = datetime.now(timezone.utc).date()

# Levels are inferred from the event slug, because the daily listing does not
# carry a level column.  Grand Slams and the tour's own naming do.
SLAM_SLUGS = {"australian-open", "french-open", "wimbledon", "us-open"}


def main() -> int:
    store: dict = read_json("results-daily.json", {}) or {}
    tournaments: dict = read_json("tournaments.json", {}) or {}

    days: list[str] = []
    for year in range(SEASON, SEASON - SEASONS, -1):
        start = date(year, 1, 1)
        end = TODAY if year == SEASON else date(year, 12, 31)
        cursor = start
        while cursor <= end:
            days.append(cursor.isoformat())
            cursor += timedelta(days=1)

    pending = [d for d in days if d not in store]
    log("results", f"{len(days)} days in range, {len(pending)} still to fetch (resuming).")
    if not pending:
        _summarise(store, tournaments)
        return 0

    for index, day in enumerate(pending, start=1):
        year, month, dom = (int(x) for x in day.split("-"))
        doc = te.get(f"{te.RESULTS_BASE}?type=atp-single&year={year}&month={month:02d}&day={dom:02d}")
        parsed = te.parse_results_day(doc)
        store[day] = {
            "tournaments": parsed["tournaments"],
            "matches": parsed["matches"],
        }
        for path, event in parsed["tournaments"].items():
            entry = tournaments.setdefault(path, {
                "path": path,
                "name": event["name"],
                "flag": event["flag"],
                "surface": event["surface"],
                "year": year,
                "dates": [],
                "matches": 0,
                "level": _level(path),
            })
            if day not in entry["dates"]:
                entry["dates"].append(day)
            entry["matches"] += event["matches"]
            if not entry["surface"] and event["surface"]:
                entry["surface"] = event["surface"]

        if index % 25 == 0:
            log("results", f"{index}/{len(pending)} days…")
            _save(store, tournaments)

    _save(store, tournaments)
    _summarise(store, tournaments)
    return 0


def _save(store: dict, tournaments: dict) -> None:
    write_json("data/results-daily.json", {k: store[k] for k in sorted(store)})
    for entry in tournaments.values():
        entry["dates"].sort()
    write_json("data/tournaments.json", {k: tournaments[k] for k in sorted(tournaments)})


def _summarise(store: dict, tournaments: dict) -> None:
    total_matches = sum(len(v["matches"]) for v in store.values())
    log("results", f"Done — {len(store)} days, {len(tournaments)} tournaments, {total_matches} matches.")


def _level(path: str) -> str:
    """
    Best-effort event level from the slug.

    The daily listing has no level column, so the slug is used: the four majors
    are named explicitly, the tour finals and the Next Gen Finals carry their own
    slugs, and the rest are labelled by the tour tier the slug implies.
    """
    slug = path.strip("/").split("/")[0]
    if slug in SLAM_SLUGS:
        return "Grand Slam"
    if "next-gen" in slug or slug in ("masters-cup", "atp-finals", "tour-finals"):
        return "Tour Finals"
    if slug.startswith(("davis-cup", "united-cup", "atp-cup")):
        return "Team Cup"
    if "challenger" in slug:
        return "Challenger"
    if slug in ("olympics", "olympic-games"):
        return "Olympics"
    return "ATP Tour"


if __name__ == "__main__":
    raise SystemExit(main())
