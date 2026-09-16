#!/usr/bin/env python3
"""
Fetch season match logs for the ranked players.

Tennis Explorer serves a player's whole season on one page
(`/player/<slug>/?annual=YYYY`), listing every match with the date, tournament,
surface, round, both players, the score and the closing odds.  The first player on
each row is the winner, which verify.py cross-checks against the independently
scraped season W/L table.

    python3 pyscripts/fetch_matches.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import te
from wtalib import env_int, log, read_json, write_json

LIMIT = env_int("ATP_MATCH_LIMIT", 300)
SEASONS = env_int("ATP_MATCH_SEASONS", 4)
WORKERS = env_int("ATP_MATCH_WORKERS", 2)
SEASON = env_int("ATP_SEASON", datetime.now(timezone.utc).year)


def main() -> int:
    rankings = read_json("rankings-singles.json", {"players": []})
    targets = rankings["players"][:LIMIT]
    if not targets:
        raise SystemExit("no rankings — run fetch_rankings.py first")

    years = list(range(SEASON, SEASON - SEASONS, -1))
    existing: dict = read_json("matches.json", {}) or {}
    out: dict = {k: v for k, v in existing.items()}

    # Resume per player: a player is only complete when every season is present.
    if existing:
        complete = {k for k, v in existing.items() if set(v.get("years", [])) >= set(years)}
        out = {k: v for k, v in existing.items() if k in complete}
        targets = [p for p in targets if p["id"] not in complete]
        if not targets:
            log("matches", f"Nothing to fetch — all {len(out)} logs already cover {years}.")
            return 0
        log("matches", f"Resuming — {len(out)} complete, {len(targets)} to fetch.")

    log("matches", f"Fetching match logs for {len(targets)} players, seasons {years}…")

    failures = 0

    def handle(player: dict) -> None:
        pid = player["id"]
        slug = pid  # the id is the full slug
        collected: list[dict] = []
        have_years: list[int] = []
        for year in years:
            doc = te.get(f"{te.PLAYER_BASE.format(slug=slug)}?annual={year}")
            rows = te.parse_match_log(doc, year, pid)
            if rows:
                have_years.append(year)
                collected.extend(rows)
        if not collected:
            raise RuntimeError("no matches returned")
        collected.sort(key=lambda m: m["date"], reverse=True)
        out[pid] = {"years": have_years, "matches": collected}

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(handle, p): p for p in targets}
        done = 0
        for future in as_completed(futures):
            player = futures[future]
            try:
                future.result()
            except Exception as err:  # noqa: BLE001
                failures += 1
                print(f"  ! {player['name']}: {err}")
            done += 1
            if done % 20 == 0:
                log("matches", f"{done}/{len(targets)}…")

    ordered = {k: out[k] for k in sorted(out, key=int)}
    write_json("data/matches.json", ordered)

    total = sum(len(v["matches"]) for v in ordered.values())
    wins = sum(1 for v in ordered.values() for m in v["matches"] if m["won"])
    log("matches", f"Done — {len(ordered)} players, {total} matches "
                   f"({wins} won, {total - wins} lost, {wins / total * 100:.1f}% wins)"
                   + (f", {failures} failures" if failures else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
