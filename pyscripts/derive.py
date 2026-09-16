#!/usr/bin/env python3
"""
Build derived aggregates from the scraped snapshots.

The ATP source publishes match results and win/loss records rather than the WTA
feed's pre-aggregated serve percentages, so the leaderboards here are built from
what the tour actually reports:

  · season win leaders and win percentage, with a minimum match count
  · title leaders, main tour and season
  · surface specialists — best win rate on each surface
  · biggest ranking climbers for the current week
  · career leaders: titles and match wins

Every figure is counted from published results; nothing is modelled.

    python3 pyscripts/derive.py
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from wtalib import env_int, log, read_json, write_json

SEASON = env_int("ATP_SEASON", datetime.now(timezone.utc).year)
MIN_MATCHES = env_int("ATP_MIN_MATCHES", 10)

SURFACES = ["Hard", "Clay", "Grass", "Indoors"]


def pct(won: int, lost: int) -> float | None:
    total = (won or 0) + (lost or 0)
    if total <= 0:
        return None
    return math.floor((won or 0) / total * 1000 + 0.5) / 10


def main() -> int:
    bios = read_json("bios.json", {}) or {}
    seasons = read_json("season-records.json", {}) or {}
    titles = read_json("titles.json", {}) or {}
    rankings = read_json("rankings-singles.json", {"players": []})
    tournaments = read_json("tournaments.json", {}) or {}

    if not bios:
        raise SystemExit("no biographies — run fetch_players.py first")

    # The daily results listing carries no surface, and neither do the draw rows;
    # only each event's own page states it.  Those pages are fetched by
    # fetch_events.py, so their metadata is merged into the calendar here.
    events = read_json("event-matches.json", {}) or {}
    backfilled = 0
    for path, draw in events.items():
        event = tournaments.get(path)
        if not event:
            continue
        for key in ("surface", "prize", "currency", "country"):
            if draw.get(key) and not event.get(key):
                event[key] = draw[key]
                backfilled += 1
    if backfilled:
        write_json("data/tournaments.json", {k: tournaments[k] for k in sorted(tournaments)})
        log("derive", f"  backfilled {backfilled} field(s) from event draws")

    log("derive", f"Building leaderboards from {len(bios)} player records…")

    rank_by_id = {p["id"]: p for p in rankings["players"]}

    def identity(pid: str) -> dict:
        bio = bios.get(pid) or {}
        player = rank_by_id.get(pid) or {}
        return {
            "id": pid,
            "name": bio.get("name") or player.get("name") or pid,
            "country": bio.get("country") or player.get("country") or "",
            "flag": bio.get("flag") or player.get("flag") or "",
            "rank": bio.get("rank") or player.get("rank"),
            "photo": bio.get("photo") or "",
        }

    def season_record(pid: str) -> dict | None:
        table = seasons.get(pid) or {}
        return table.get(str(SEASON)) or table.get(SEASON)

    def title_totals(pid: str) -> dict:
        rows = titles.get(pid) or []
        return {
            "main": sum(r.get("main", 0) for r in rows),
            "lower": sum(r.get("lower", 0) for r in rows),
            "season": sum(r.get("main", 0) for r in rows if r.get("year") == SEASON),
        }

    boards: list[dict] = []

    # ------------------------------------------------- season win leaders
    season_rows = []
    for pid in bios:
        record = season_record(pid)
        if not record or not record.get("total"):
            continue
        won, lost = record["total"]["w"], record["total"]["l"]
        if won + lost < MIN_MATCHES:
            continue
        season_rows.append({**identity(pid), "w": won, "l": lost,
                            "value": won, "matches": won + lost, "pct": pct(won, lost)})
    season_rows.sort(key=lambda r: (-r["value"], -(r["pct"] or 0)))

    boards.append({
        "key": "seasonWins", "label": "Season wins", "unit": "", "min": MIN_MATCHES,
        "note": f"{SEASON} 赛季胜场数（至少 {MIN_MATCHES} 场）。",
        "rows": season_rows[:20],
    })

    by_pct = [r for r in season_rows if r["pct"] is not None]
    by_pct.sort(key=lambda r: (-r["pct"], -r["value"]))
    boards.append({
        "key": "seasonWinPct", "label": "Season win rate", "unit": "%", "min": MIN_MATCHES,
        "note": f"{SEASON} 赛季胜率（至少 {MIN_MATCHES} 场）。",
        "rows": [dict(r, value=r["pct"]) for r in by_pct[:20]],
    })

    # ------------------------------------------------------------- titles
    title_rows = []
    for pid in bios:
        totals = title_totals(pid)
        if totals["main"] <= 0:
            continue
        title_rows.append({**identity(pid), **totals, "value": totals["main"]})
    title_rows.sort(key=lambda r: -r["value"])
    boards.append({
        "key": "careerTitles", "label": "Career titles", "unit": "", "min": 0,
        "note": "职业生涯主巡回赛单打冠军总数。",
        "rows": title_rows[:20],
    })

    season_title_rows = [dict(r, value=r["season"]) for r in title_rows if r["season"] > 0]
    season_title_rows.sort(key=lambda r: (-r["value"], -r["main"]))
    boards.append({
        "key": "seasonTitles", "label": f"{SEASON} titles", "unit": "", "min": 0,
        "note": f"{SEASON} 赛季主巡回赛单打冠军数。",
        "rows": season_title_rows[:20],
    })

    # ------------------------------------------------- surface specialists
    for surface in SURFACES:
        rows = []
        for pid in bios:
            record = season_record(pid)
            if not record:
                continue
            split = (record.get("bySurface") or {}).get(surface)
            if not split or split["w"] + split["l"] < 5:
                continue
            rows.append({**identity(pid), "w": split["w"], "l": split["l"],
                         "value": pct(split["w"], split["l"]), "matches": split["w"] + split["l"]})
        if len(rows) < 5:
            continue
        rows.sort(key=lambda r: (-(r["value"] or 0), -(r["w"] + r["l"])))
        boards.append({
            "key": f"surface{surface}", "label": f"{surface} win rate", "unit": "%", "min": 5,
            "note": f"{SEASON} 赛季{surface}场地胜率（至少 5 场）。",
            "rows": rows[:20],
        })

    # ------------------------------------------------------ ranking climbers
    climbers = [
        {**identity(pid), "value": p.get("move") or 0}
        for pid, p in rank_by_id.items()
        if (p.get("move") or 0) > 0
    ]
    climbers.sort(key=lambda r: -r["value"])
    if len(climbers) >= 5:
        boards.append({
            "key": "climbers", "label": "Ranking climbers", "unit": "", "min": 0,
            "note": "本周排名上升幅度最大的球员（与上周官方排名对比）。",
            "rows": climbers[:20],
        })

    # ------------------------------------------------------------- career
    career = [b for b in bios.values() if (b.get("career") or {}).get("w")]
    career_wins = [
        {**identity(b["id"]), "value": b["career"]["w"],
         "l": b["career"]["l"], "pct": pct(b["career"]["w"], b["career"]["l"])}
        for b in sorted(career, key=lambda b: -b["career"]["w"])[:15]
    ]
    career_pct = [
        {**identity(b["id"]), "value": pct(b["career"]["w"], b["career"]["l"]),
         "w": b["career"]["w"], "l": b["career"]["l"]}
        for b in career
        if b["career"]["w"] + b["career"]["l"] >= 100
    ]
    career_pct.sort(key=lambda r: -(r["value"] or 0))

    write_json("data/leaderboards.json", {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "season": SEASON,
        "minMatches": MIN_MATCHES,
        "boards": boards,
        "career": {
            "titles": [dict(r, value=r["main"]) for r in title_rows[:15]],
            "careerWins": career_wins,
            "careerPct": career_pct[:15],
        },
    })

    log("derive", f"Done — {len(boards)} leaderboards ({', '.join(b['key'] for b in boards)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
