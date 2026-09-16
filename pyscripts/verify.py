#!/usr/bin/env python3
"""
Verify the scraped snapshots.

The most valuable assertion here is the cross-check between the two places the
source reports a player's season record: the profile's win/loss table and the
match log built from the daily results crawl.  They are scraped from different
pages, so agreement is strong evidence that both parsers are right.

    python3 pyscripts/verify.py
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

from wtalib import read_json

PASSED = 0
FAILURES: list[str] = []
SEASON = datetime.now(timezone.utc).year


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILURES.append(f"{name}{f' — {detail}' if detail else ''}")
        print(f"  ✗ {name}{f' — {detail}' if detail else ''}")


def main() -> int:
    print("\n▶ Verifying ATP snapshots\n")

    rankings = read_json("rankings-singles.json", {})
    bios = read_json("bios.json", {}) or {}
    seasons = read_json("season-records.json", {}) or {}
    titles = read_json("titles.json", {}) or {}
    daily = read_json("results-daily.json", {}) or {}
    tournaments = read_json("tournaments.json", {}) or {}
    events = read_json("event-matches.json", {}) or {}
    boards = read_json("leaderboards.json", {}) or {}
    h2h = read_json("h2h.json", {}) or {}

    # ----------------------------------------------------------- rankings
    players = rankings.get("players", [])
    check("rankings have an as-of date", bool(re.match(r"^\d{4}-\d{2}-\d{2}", rankings.get("asOf") or "")))
    check("rankings depth >= 250", len(players) >= 250, str(len(players)))
    check("rankings are a clean 1..N sequence", all(p["rank"] == i + 1 for i, p in enumerate(players)))
    check("every ranked player has a name, country and id",
          all(p["name"].strip() and p["country"].strip() and p["id"] for p in players))
    check("points are non-increasing with rank",
          all(players[i - 1]["points"] >= p["points"] for i, p in enumerate(players) if i))
    check("ids are unique", len({p["id"] for p in players}) == len(players))
    check("movement is an integer", all(isinstance(p["move"], int) for p in players))

    # --------------------------------------------------------- biographies
    check("biographies cover the ranking depth", len(bios) >= len(players) * 0.98, str(len(bios)))
    top = str(players[0]["id"]) if players else ""
    check("top player has career totals", bool((bios.get(top) or {}).get("career", {}).get("w")))
    # A player outside the top tier can legitimately have lost more than they won.
    check("career totals are present and plausible",
          all(0 < (b["career"]["w"] + b["career"]["l"]) <= 2000
              and b["career"]["w"] > 0
              for b in bios.values() if (b.get("career") or {}).get("w")))
    check("birthdates parse", all(re.match(r"^\d{4}-\d{2}-\d{2}$", b["birth"])
                                  for b in bios.values() if b.get("birth")))
    # Photos are stored as source-relative paths and prefixed with the host when
    # rendered, so the path shape is what matters here.
    check("photo paths point at the source image folder",
          all(b["photo"].startswith(("/res/img/player/", "http")) for b in bios.values() if b.get("photo")))

    # ------------------------------- season records add up per surface
    mismatched = []
    for pid, table in seasons.items():
        for year, record in table.items():
            total = record.get("total")
            splits = record.get("bySurface") or {}
            if not total or not splits:
                continue
            if (sum(s["w"] for s in splits.values()) != total["w"]
                    or sum(s["l"] for s in splits.values()) != total["l"]):
                mismatched.append(f"{pid}/{year}")
    check("per-surface records sum to the season total", not mismatched, ",".join(mismatched[:4]))

    # ------------------------------------------------- daily results crawl
    check("daily results cover a season", len(daily) >= 200, f"{len(daily)} days")
    total_matches = sum(len(v["matches"]) for v in daily.values())
    check("daily results hold a substantial match count", total_matches >= 20000, str(total_matches))
    bad = [d for d, v in daily.items() if any(not m["winner"]["id"] or not m["loser"]["id"] for m in v["matches"])]
    check("every stored match names both players", not bad, ",".join(sorted(bad)[:3]))
    self_play = [d for d, v in daily.items()
                 if any(m["winner"]["id"] == m["loser"]["id"] for m in v["matches"])]
    check("no match pairs a player with themselves", not self_play, ",".join(sorted(self_play)[:3]))
    check("result rows carry a score",
          all(" ".join(m.get("score") or "").strip() for v in daily.values() for m in v["matches"]))

    # ------------------------------------------ the decisive cross-check
    # Compare the profile's season record with the season record implied by the
    # daily results for the same player.
    from collections import defaultdict
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for day, payload in daily.items():
        if not day.startswith(str(SEASON)):
            continue
        for match in payload["matches"]:
            tally[match["winner"]["id"]][0] += 1
            tally[match["loser"]["id"]][1] += 1

    compared = exact = close = 0
    for pid, table in seasons.items():
        record = table.get(str(SEASON)) or table.get(SEASON)
        if not record or not record.get("total"):
            continue
        won, lost = record["total"]["w"], record["total"]["l"]
        if won + lost < 20:
            continue
        counted = tally.get(pid)
        if not counted or counted[0] + counted[1] < 20:
            continue
        compared += 1
        if counted[0] == won and counted[1] == lost:
            exact += 1
        if abs(counted[0] - won) <= 2 and abs(counted[1] - lost) <= 2:
            close += 1
    check("profile season W/L reconciles with the results crawl",
          compared >= 50 and close / compared >= 0.9,
          f"{exact}/{compared} exact, {close}/{compared} within 2")

    # ------------------------------------------------------------ titles
    check("titles were parsed", sum(1 for t in titles.values() if t) >= 150)
    check("title rows carry a year and a count",
          all(t.get("year") and (t.get("main") or t.get("lower")) is not None
              for rows in titles.values() for t in rows))

    # --------------------------------------------- tournaments and events
    check("calendar holds many events", len(tournaments) >= 150, str(len(tournaments)))
    check("every event has dates", all(t.get("dates") for t in tournaments.values()))
    # A few exhibition series publish no surface, and one event's page is missing
    # entirely; the rest must have one, since the calendar displays it.
    with_surface = sum(1 for t in tournaments.values() if t.get("surface"))
    check("almost every event has a surface",
          with_surface >= len(tournaments) * 0.97,
          f"{with_surface}/{len(tournaments)}")
    check("event dates are ISO", all(re.match(r"^\d{4}-\d{2}-\d{2}$", d)
                                     for t in tournaments.values() for d in t["dates"]))
    check("draws were fetched", len(events) >= 100, str(len(events)))
    finals = [r for e in events.values() for r in e["rounds"] if r["code"] == "F"]
    check("most draws reach a final", len(finals) >= len(events) * 0.8,
          f"{len(finals)}/{len(events)}")
    check("finals hold exactly one match", all(len(r["matches"]) == 1 for r in finals))
    check("every draw match names a winner and a loser",
          all(m["winner"]["id"] and m["loser"]["id"] and m["winner"]["id"] != m["loser"]["id"]
              for e in events.values() for r in e["rounds"] for m in r["matches"]))
    # A knockout round of n matches implies n*2 entrants.
    ladder = {"F": 1, "SF": 2, "QF": 4, "R16": 8, "R32": 16, "R64": 32, "R128": 64}
    odd = [f'{e["name"]}/{r["code"]}'
           for e in events.values() for r in e["rounds"]
           if r["code"] in ladder and len(r["matches"]) != ladder[r["code"]]]
    check("draw rounds have the size their code implies", not odd,
          f"{len(odd)} off (e.g. {odd[:2]})")

    # -------------------------------------------------------- leaderboards
    check("leaderboards were built", len(boards.get("boards", [])) >= 8, str(len(boards.get("boards", []))))
    check("every board is sorted by value",
          all(all((b["rows"][i - 1]["value"] or 0) >= (r["value"] or 0)
                  for i, r in enumerate(b["rows"]) if i) for b in boards.get("boards", [])))
    check("career leaders present",
          all(len(boards.get("career", {}).get(k, [])) >= 5
              for k in ("titles", "careerWins", "careerPct")))

    # ---------------------------------------------------------------- h2h
    check("head-to-head index built", len(h2h) > 5000, str(len(h2h)))
    check("pair keys are ordered a<b",
          all(k.split("|", 1)[0] < k.split("|", 1)[1] for k in h2h if "|" in k))
    check("win totals equal the recorded meeting count",
          all(v["aWins"] + v["bWins"] == v.get("n", len(v["meetings"])) for v in h2h.values()))
    check("meetings name a winner and a loser",
          all(m["w"] and m["lo"] and m["w"] != m["lo"] for v in h2h.values() for m in v["meetings"]))

    print("\n" + "─" * 60)
    if FAILURES:
        print(f"✗ {len(FAILURES)} check(s) failed, {PASSED} passed:")
        for line in FAILURES:
            print(f"   • {line}")
        return 1
    print(f"✓ All {PASSED} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
