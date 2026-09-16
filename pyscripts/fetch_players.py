#!/usr/bin/env python3
"""
Fetch per-player records.

For every ranked player one page carries three things at once:

  · the `plDetail` card  — country, height/weight, age and birthdate, handedness,
                           current and career-high ranking
  · the `balance` table  — W/L for every season, split by surface, plus the
                           career totals
  · the `titles` table   — titles per season, main tour and lower level, with the
                           event names

Match-by-match logs are fetched separately by fetch_matches.py.

    python3 pyscripts/fetch_players.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import te
from wtalib import env_int, log, read_json, write_json

LIMIT = env_int("ATP_PLAYER_LIMIT", 300)
WORKERS = env_int("ATP_PLAYER_WORKERS", 2)


def main() -> int:
    rankings = read_json("rankings-singles.json", {"players": []})
    targets = rankings["players"][:LIMIT]
    if not targets:
        raise SystemExit("no rankings — run fetch_rankings.py first")

    # Resume: records already stored are not re-fetched.
    bios: dict = read_json("bios.json", {}) or {}
    balances: dict = read_json("season-records.json", {}) or {}
    titles: dict = read_json("titles.json", {}) or {}
    targets = [p for p in targets if p["id"] not in bios]
    if not targets:
        log("players", f"Nothing to fetch — all {len(bios)} records already present.")
        return 0

    log("players", f"Fetching records for {len(targets)} players…")

    failures = 0

    def handle(player: dict) -> None:
        # The id IS the full slug the site uses in its links.
        doc = te.get(te.PLAYER_BASE.format(slug=player["id"]))
        if not doc:
            raise RuntimeError("empty page")

        detail = te.parse_player_detail(doc)
        balance = te.parse_player_balance(doc)
        won_titles = te.parse_player_titles(doc)

        bios[player["id"]] = {
            "id": player["id"],
            "slug": player["slug"],
            "name": player["name"],
            "country": detail.get("country") or player["country"],
            "flag": player.get("flag") or "",
            "rank": detail.get("rank") or player["rank"],
            "highRank": detail.get("highRank"),
            "highRankDoubles": detail.get("highRankDoubles"),
            "points": player["points"],
            "move": player["move"],
            "age": detail.get("age"),
            "birth": detail.get("birth") or "",
            "height": detail.get("height"),
            "weight": detail.get("weight"),
            "hand": detail.get("hand") or "",
            "photo": detail.get("photo") or "",
            "career": (balance.get("career") or {}).get("total") or {},
            "careerBySurface": (balance.get("career") or {}).get("bySurface") or {},
        }
        balances[player["id"]] = balance.get("seasons") or {}
        titles[player["id"]] = won_titles

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
            if done % 25 == 0:
                log("players", f"{done}/{len(targets)}…")

    # Newest-first player ids for stable diffs.
    write_json("data/bios.json", {k: bios[k] for k in sorted(bios)})
    write_json("data/season-records.json", {k: balances[k] for k in sorted(balances)})
    write_json("data/titles.json", {k: titles[k] for k in sorted(titles)})

    total_titles = sum(t.get("main", 0) for rows in titles.values() for t in rows)
    log("players", f"Done — {len(bios)} biographies, {len(balances)} season records, "
                   f"{total_titles} main-tour titles" + (f", {failures} failures" if failures else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
