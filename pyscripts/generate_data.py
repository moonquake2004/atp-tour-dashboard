#!/usr/bin/env python3
"""
Build the data files the dashboard consumes.

Everything is derived from the scraped snapshots in ``data/`` — no network calls —
so the site is reproducible offline.  Four files are written:

``data/atp.js``          the main payload: meta, players, results, champions, calendar
``data/atp-events.js``   complete per-event draws, loaded on demand
``data/atp-h2h.js``      head-to-head summary for every pairing
``data/atp-h2h-matches.js``  the individual meetings, loaded on demand

They are plain scripts assigning a global, so the published site needs no runtime
fetches for content.

    python3 pyscripts/generate_data.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from wtalib import ROOT, env_int, log, read_json, score_text

SEASON = env_int("ATP_SEASON", datetime.now(timezone.utc).year)
# The feed is the season's most recent results; the rest stay reachable through
# each player's profile and each event's draw, so the page does not need to carry
# thousands of rows.
RESULT_LIMIT = env_int("ATP_RESULT_LIMIT", 600)
MAX_PAIR_MEETINGS = env_int("ATP_H2H_MAX", 24)

# Exhibition and training series that the source lists alongside tour events.
# They run intermittently all season, so a "tournament" built from them would
# span hundreds of days, and they are not part of the ATP calendar.
EXHIBITION_MARKERS = ("utr pro tennis series", "ultimate tennis showdown",
                      "exhibition", "- exh.")


def write_global(rel_path: str, global_name: str, value, *, comment: str) -> int:
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (f"/* {comment} */\n"
            f"window.{global_name}={json.dumps(value, ensure_ascii=False, separators=(',', ':'))};\n")
    path.write_text(body, encoding="utf-8")
    size = len(body.encode())
    log("gen", f"  ✓ {rel_path} ({size / 1024 / 1024:.2f} MB)")
    return size


def main() -> int:
    log("gen", "Building the dashboard payload…")

    rankings = read_json("rankings-singles.json", {"players": [], "asOf": None, "depth": 0})
    bios = read_json("bios.json", {}) or {}
    seasons = read_json("season-records.json", {}) or {}
    titles = read_json("titles.json", {}) or {}
    events = read_json("event-matches.json", {}) or {}
    tournaments = read_json("tournaments.json", {}) or {}
    calendar_src = (read_json("calendar.json", {}) or {}).get("events") or []
    daily = read_json("results-daily.json", {}) or {}
    boards_in = read_json("leaderboards.json", {"boards": [], "career": {}}) or {}
    h2h = read_json("h2h.json", {}) or {}
    h2h_names = read_json("h2h-names.json", {}) or {}
    zh = read_json("zh.json", {}) or {}

    zh_players = zh.get("players") or {}
    zh_tournaments = zh.get("tournaments") or {}
    zh_countries = zh.get("countries") or {}

    rank_by_id = {p["id"]: p for p in rankings["players"]}

    def zh_name(pid) -> str:
        return str(zh_players.get(str(pid), "") or "").strip()

    def display(pid: str) -> dict:
        """Resolve any player id to name, Chinese name, country, flag, rank."""
        player = rank_by_id.get(pid)
        bio = bios.get(pid) or {}
        entry = h2h_names.get(pid) or {}
        return {
            "id": pid,
            "name": bio.get("name") or (player or {}).get("name") or entry.get("n") or f"#{pid}",
            "zh": zh_name(pid),
            "country": bio.get("country") or (player or {}).get("country") or entry.get("c") or "",
            "flag": bio.get("flag") or (player or {}).get("flag") or entry.get("f") or "",
            "rank": bio.get("rank") or (player or {}).get("rank") or entry.get("r"),
            "photo": bio.get("photo") or entry.get("p") or "",
        }

    # ------------------------------------------------------------- players
    players_out = []
    for player in rankings["players"]:
        pid = player["id"]
        bio = bios.get(pid) or {}
        table = seasons.get(pid) or {}
        record = table.get(str(SEASON)) or table.get(SEASON) or {}
        won_titles = titles.get(pid) or []
        players_out.append({
            "id": pid,
            "slug": player.get("slug") or bio.get("slug") or "",
            "name": player["name"],
            "zh": zh_name(pid),
            "country": bio.get("country") or player["country"],
            "flag": player.get("flag") or "",
            "rank": player["rank"],
            "points": player["points"],
            "move": player["move"],
            "age": bio.get("age"),
            "birth": bio.get("birth") or "",
            "height": bio.get("height"),
            "weight": bio.get("weight"),
            "hand": bio.get("hand") or "",
            "highRank": bio.get("highRank"),
            "photo": bio.get("photo") or "",
            "career": bio.get("career") or {},
            "careerBySurface": bio.get("careerBySurface") or {},
            "season": {
                "w": (record.get("total") or {}).get("w"),
                "l": (record.get("total") or {}).get("l"),
                "bySurface": record.get("bySurface") or {},
                "titles": sum(t.get("main", 0) for t in won_titles if t.get("year") == SEASON),
            } if record.get("total") else None,
            "titles": {
                "main": sum(t.get("main", 0) for t in won_titles),
                "lower": sum(t.get("lower", 0) for t in won_titles),
                "byYear": [{"year": t["year"], "main": t["main"], "lower": t["lower"],
                            "events": t.get("events") or []} for t in sorted(won_titles, key=lambda x: -x["year"])[:12]],
            },
            "seasons": [{"year": int(y), "w": (r.get("total") or {}).get("w"),
                         "l": (r.get("total") or {}).get("l")}
                        for y, r in sorted(table.items(), key=lambda kv: -int(kv[0]))[:12]
                        if r.get("total")],
        })

    # ------------------------------------------------------ results feed
    results = []
    for day in sorted(daily, reverse=True):
        for match in daily[day]["matches"]:
            winner, loser = match.get("winner") or {}, match.get("loser") or {}
            if not winner.get("id") or not loser.get("id"):
                continue
            lowered_event = (match.get("tournament") or "").lower()
            if any(marker in lowered_event for marker in EXHIBITION_MARKERS):
                continue
            results.append({
                "date": day,
                "event": match["tournament"],
                "zh": zh_tournaments.get(match["tournament"], ""),
                "path": match.get("tournamentPath", ""),
                "surface": _surface_of(tournaments, match.get("tournamentPath", ""), day),
                "level": _level_of(tournaments, match.get("tournamentPath", "")),
                "score": score_text(match.get("score")),
                "winner": display(winner["id"]),
                "loser": display(loser["id"]),
                "seedW": winner.get("seed", ""),
                "seedL": loser.get("seed", ""),
            })
    recent = results[:RESULT_LIMIT]

    # ---------------------------------------------------------- champions
    champions = []
    for key, event in events.items():
        final = next((r for r in event["rounds"] if r["code"] == "F"), None)
        if not final or not final["matches"]:
            continue
        match = final["matches"][0]
        winner = display(match["winner"]["id"])
        champions.append({
            "event": event["name"],
            "zh": zh_tournaments.get(event["name"], ""),
            "path": event["path"],
            "year": event["year"],
            "date": max(event.get("dates") or ["", ""]) if event.get("dates") else "",
            "level": event.get("level") or "",
            "surface": event.get("surface") or "",
            "flag": event.get("flag") or "",
            "player": winner,
            "runnerUp": display(match["loser"]["id"]),
            "score": score_text(match.get("score")),
        })
    champions.sort(key=lambda c: (c["date"], c["event"]), reverse=True)

    # ----------------------------------------------------------- calendar
    # The calendar page is the authoritative source: it also lists events that
    # have not been played yet, which the results crawl cannot see.  The crawl
    # still supplies the match count and the day span for events it covered.
    calendar = []
    for event in calendar_src:
        lowered = event["name"].lower()
        if any(marker in lowered for marker in EXHIBITION_MARKERS) or event.get("level") == "Exhibition":
            continue
        crawled = tournaments.get(event["path"]) or {}
        dates = sorted(crawled.get("dates") or [])
        champion = next((c for c in champions if c["path"] == event["path"]), None)
        calendar.append({
            "path": event["path"],
            "name": event["name"],
            "zh": zh_tournaments.get(event["name"], ""),
            "year": event["year"],
            "level": event.get("level") or "",
            "surface": event.get("surface") or crawled.get("surface") or "",
            "currency": event.get("currency") or "",
            "prize": event.get("prize"),
            "draw": event.get("draw"),
            "flag": crawled.get("flag") or "",
            "start": dates[0] if dates else event["date"],
            "end": dates[-1] if dates else event["date"],
            "days": len(dates) or 1,
            "matches": crawled.get("matches") or 0,
            "played": bool(champion) or event.get("played") or False,
            "champion": champion["player"] if champion else (
                {"id": event["winner"]["id"], "name": event["winner"]["name"],
                 "zh": zh_name(event["winner"]["id"]), "country": "", "flag": "",
                 "rank": None, "photo": ""} if event.get("winner") else None),
        })
    calendar.sort(key=lambda e: (e["start"], e["name"]), reverse=True)

    # ---------------------------------------------------------------- h2h
    roster: dict = {}
    for player in rankings["players"]:
        info = display(player["id"])
        roster[player["id"]] = {
            "id": player["id"], "name": info["name"], "zh": info["zh"],
            "country": info["country"], "flag": info["flag"], "rank": info["rank"],
            "photo": info["photo"],
        }

    pairs: dict = {}
    meetings_out: dict = {}
    for key, value in h2h.items():
        a, b = key.split("|", 1)
        for pid in (a, b):
            if pid not in roster:
                info = display(pid)
                roster[pid] = {"id": pid, "name": info["name"], "zh": info["zh"],
                               "country": info["country"], "flag": info["flag"],
                               "rank": info["rank"], "photo": info["photo"]}
        pairs[key] = {"aw": value["aWins"], "bw": value["bWins"], "n": value.get("n", 0)}
        rows = []
        for meeting in value["meetings"][:MAX_PAIR_MEETINGS]:
            rows.append([meeting["d"], meeting["t"], zh_tournaments.get(meeting["t"], ""),
                         meeting.get("sc", ""), meeting["w"]])
        if rows:
            meetings_out[key] = rows

    # Leaderboard rows are built by derive.py before the Chinese names exist (zh
    # runs after derive), so every row is injected here, mirroring the WTA
    # builder's with_zh.  Rows whose only "Chinese" label is the Latin name keep
    # the empty field and the templates fall back to the English name.
    def with_zh(row: dict) -> dict:
        return dict(row, zh=zh_name(row.get("id")))

    boards_out = [
        {**b, "rows": [with_zh(r) for r in b.get("rows") or []]}
        for b in boards_in.get("boards") or []
    ]
    career_out = {
        k: [with_zh(r) for r in rows]
        for k, rows in (boards_in.get("career") or {}).items()
    }
    season_events = [e for e in calendar if e["year"] == SEASON]
    meta = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "season": SEASON,
        "rankingsAsOf": rankings.get("asOf"),
        "tour": "ATP",
        "source": "Tennis Explorer (ATP rankings, results and draws)",
        "sourceUrl": "https://www.tennisexplorer.com/ranking/atp-men/",
        "depth": rankings.get("depth"),
        "counts": {
            "rankedPlayers": len(rankings["players"]),
            "events": len(season_events),
            "seasonMatches": len(results),
            "calendarEvents": len(calendar),
            "champions": sum(1 for c in champions if c["year"] == SEASON),
            "eventDraws": len(events),
            "h2hPairings": len(pairs),
            "namedPlayers": len(roster),
        },
        "zh": {
            "countries": zh_countries,
            "rounds": zh.get("rounds") or {},
            "surfaces": zh.get("surfaces") or {},
            "levels": zh.get("levels") or {},
        },
    }

    payload = {
        "meta": meta,
        "players": players_out,
        "results": recent,
        "champions": champions,
        "calendar": calendar,
        "boards": boards_out,
        "career": career_out,
        "tournamentZh": zh_tournaments,
        "playerIndex": [{"i": p["id"], "n": p["name"], "c": p["country"], "r": p["rank"],
                         "p": p["points"]} for p in rankings["players"]],
    }

    stamp = meta["generatedAt"]
    write_global("data/atp.js", "ATP_DATA", payload,
                 comment=f"ATP Tour dashboard data — generated {stamp}")
    write_global("data/atp-events.js", "ATP_EVENTS", events,
                 comment=f"Per-event draws — generated {stamp}")
    write_global("data/atp-h2h.js", "ATP_H2H", {"players": roster, "pairs": pairs},
                 comment=f"Head-to-head summary — generated {stamp}")
    write_global("data/atp-h2h-matches.js", "ATP_H2H_MATCHES", meetings_out,
                 comment=f"Head-to-head meetings — generated {stamp}")

    counts = meta["counts"]
    log("gen", f"Done — {len(players_out)} players, {len(recent)} season results, "
               f"{len(calendar)} calendar events, {counts['champions']} champions")
    log("gen", f"  {len(events)} draws · {len(pairs)} H2H pairings · {len(roster)} named players")
    return 0


def _find_event(tournaments: dict, path: str) -> dict | None:
    return tournaments.get(path) if path else None


def _surface_of(tournaments: dict, path: str, day: str) -> str:
    event = _find_event(tournaments, path)
    return (event or {}).get("surface") or ""


def _level_of(tournaments: dict, path: str) -> str:
    return (tournaments.get(path) or {}).get("level") or ""


if __name__ == "__main__":
    raise SystemExit(main())
