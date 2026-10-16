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

    _finalise(store, tournaments)
    _summarise(store, tournaments)
    return 0


def _save(store: dict, tournaments: dict) -> None:
    write_json("data/results-daily.json", {k: store[k] for k in sorted(store)})
    for entry in tournaments.values():
        entry["dates"].sort()
    write_json("data/tournaments.json", {k: tournaments[k] for k in sorted(tournaments)})


def _finalise(store: dict, tournaments: dict) -> None:
    """Idempotent closing step: recompute match totals, guard the caps, persist."""
    _recompute_matches(store, tournaments)
    _enforce_caps(tournaments)
    _save(store, tournaments)


def _recompute_matches(store: dict, tournaments: dict) -> None:
    """Rebuild every tournament's match count from the stored days.

    The total used to be accumulated while crawling, which duplicated matches
    whenever a run resumed over days that had already been counted — the
    biella-challenger 1001-match anomaly.  Recomputing from the store makes the
    count idempotent: each (day, tournament) pair contributes exactly the matches
    parsed for that day.
    """
    for entry in tournaments.values():
        entry["matches"] = 0
    for day_value in store.values():
        for path, event in (day_value.get("tournaments") or {}).items():
            entry = tournaments.get(path)
            if entry is None:
                continue
            entry["matches"] += event.get("matches") or 0


# Upper bounds for the number of completed singles matches an event of a given
# level can plausibly contain.  The main draw of a Challenger caps at 128
# (64 first-round matches), so any count near 1001 is a crawl artefact, not data.
LEVEL_MATCH_CAPS = {
    "Grand Slam": 127,
    "ATP Tour": 127,
    "Challenger": 127,
    "Tour Finals": 15,
    "Olympics": 63,
    "Team Cup": 300,
}
DEFAULT_MATCH_CAP = 127


def _cap_for(level: str) -> int:
    return LEVEL_MATCH_CAPS.get(level, DEFAULT_MATCH_CAP)


def _enforce_caps(tournaments: dict) -> None:
    """Clamp and loudly log implausible match totals so they cannot pass silently."""
    for path, entry in tournaments.items():
        cap = _cap_for(entry.get("level") or "")
        total = entry.get("matches") or 0
        if total > cap:
            log("results", f"CAP exceeded: {path} reports {total} matches "
                           f"(> {cap} for level {entry.get('level')!r}); clamping to {cap}.")
            entry["matches"] = cap


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
