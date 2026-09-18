#!/usr/bin/env python3
"""
Fetch the official ATP singles ranking.

Source: Tennis Explorer's ATP ranking table, which republishes the ATP's weekly
list with position movement and points.  Each page holds 50 players.

    python3 pyscripts/fetch_rankings.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import te
from wtalib import env_int, log, read_json, write_json

DEPTH = env_int("ATP_RANK_DEPTH", 300)
PER_PAGE = 50


def main() -> int:
    pages = (DEPTH + PER_PAGE - 1) // PER_PAGE
    log("rankings", f"Fetching the ATP singles ranking (depth {DEPTH}, {pages} pages)…")

    players: list[dict] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        doc = te.get(f"{te.RANK_BASE}?page={page}")
        rows = te.parse_rankings(doc)
        if not rows:
            log("rankings", f"  page {page} returned nothing — stopping")
            break
        for row in rows:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            players.append(row)
        log("rankings", f"  page {page}: {len(rows)} rows (total {len(players)})")

    # Renumber: the ranking is the source of truth for order, and a page boundary
    # should never produce a duplicate or a gap.
    for index, player in enumerate(players, start=1):
        player["rank"] = index

    payload = {
        "source": "Tennis Explorer (republished ATP rankings)",
        "sourceUrl": "https://www.tennisexplorer.com/ranking/atp-men/",
        "tour": "ATP",
        "asOf": _rankings_date(),
        "generatedAt": _now(),
        "depth": len(players),
        "players": players,
    }
    write_json("data/rankings-singles.json", payload)
    write_json(
        "data/players-index.json",
        [{"i": p["id"], "n": p["name"], "c": p["country"], "r": p["rank"], "p": p["points"]}
         for p in players],
    )

    top = players[0] if players else None
    log("rankings", f"Done — {len(players)} players"
                    + (f", No.1 {top['name']} ({top['points']} pts)" if top else ""))
    return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _rankings_date() -> str:
    """
    The publication date of the ranking week.

    Tennis Explorer stamps its pages with the current date; the ATP publishes on
    Mondays, so the snapshot is attributed to the Monday of the current week.
    """
    today = datetime.now(timezone.utc).date()
    monday = today.fromordinal(today.toordinal() - today.weekday())
    return monday.isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
