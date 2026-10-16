#!/usr/bin/env python3
"""
Fold every stored result into a pairwise head-to-head index.

Because the daily crawl captures every completed match across every event, this
index is built from the complete result set rather than from the ranked players'
own logs — so a pairing is known even when neither player is in the top 300.

Win counts are authoritative and never truncated; only the displayed meeting list
is capped.

    python3 pyscripts/fetch_h2h.py
"""

from __future__ import annotations

from wtalib import env_int, log, read_json, write_json

MAX_MEETINGS = env_int("ATP_H2H_MAX", 24)


# A player id may itself contain a dash (some slugs end in an empty segment, so
# the whole slug becomes the id), which rules out "-" as the pair separator.
SEP = "|"


def pair_key(a: str, b: str) -> str:
    """Smaller id first, so both directions land in one bucket."""
    return f"{a}{SEP}{b}" if a < b else f"{b}{SEP}{a}"


def main() -> int:
    daily = read_json("results-daily.json", {}) or {}
    bios = read_json("bios.json", {}) or {}
    rankings = read_json("rankings-singles.json", {"players": []})

    if not daily:
        raise SystemExit("no results — run fetch_results.py first")

    log("h2h", f"Folding {len(daily)} days of results into a head-to-head index…")

    names: dict = {}
    for player in rankings["players"]:
        names[player["id"]] = {"n": player["name"], "c": player["country"],
                               "f": player.get("flag", ""), "r": player["rank"],
                               "p": bios.get(player["id"], {}).get("photo", "")}
    for pid, bio in bios.items():
        names.setdefault(pid, {"n": bio.get("name", ""), "c": bio.get("country", ""),
                               "f": bio.get("flag", ""), "r": bio.get("rank"),
                               "p": bio.get("photo", "")})

    pairs: dict = {}
    meetings = 0
    seen: set[str] = set()

    for day in sorted(daily):
        for match in daily[day]["matches"]:
            winner, loser = match["winner"], match["loser"]
            wid, lid = winner.get("id"), loser.get("id")
            if not wid or not lid or wid == lid:
                continue

            # The same match appears once per day it was listed; de-duplicate.
            dedup = f"{day}|{wid}|{lid}|{score_text(match.get('score'))}"
            if dedup in seen:
                continue
            seen.add(dedup)

            key = pair_key(wid, lid)
            bucket = pairs.get(key)
            if bucket is None:
                bucket = {"a": min(wid, lid), "b": max(wid, lid),
                          "aWins": 0, "bWins": 0, "meetings": []}
                pairs[key] = bucket

            if wid == bucket["a"]:
                bucket["aWins"] += 1
            else:
                bucket["bWins"] += 1
            meetings += 1

            bucket["meetings"].append({
                "d": day,
                "t": match["tournament"],
                "tp": match.get("tournamentPath", ""),
                "sc": score_text(match.get("score")),
                "w": wid,
                "lo": lid,
                "seedW": winner.get("seed", ""),
                "seedL": loser.get("seed", ""),
            })

            for side, role in ((winner, "w"), (loser, "l")):
                pid = side.get("id")
                if pid and pid not in names:
                    names[pid] = {"n": side.get("name", ""), "c": "", "f": "",
                                  "r": None, "p": ""}

    out: dict = {}
    for key, bucket in pairs.items():
        bucket["meetings"].sort(key=lambda m: m["d"], reverse=True)
        bucket["n"] = len(bucket["meetings"])
        if len(bucket["meetings"]) > MAX_MEETINGS:
            bucket["meetings"] = bucket["meetings"][:MAX_MEETINGS]
        out[key] = bucket

    write_json("data/h2h.json", out)
    write_json("data/h2h-names.json", names)

    log("h2h", f"Done — {len(out)} pairings, {meetings} meetings, {len(names)} named players.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
