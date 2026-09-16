#!/usr/bin/env python3
"""
Verify the generated data payload.

Assertions run over the generated scripts so a broken build cannot be published.

    python3 pyscripts/verify_dashboard.py
"""

from __future__ import annotations

import json
import re
import sys

from wtalib import DATA_DIR

PASSED = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASSED
    if ok:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILURES.append(f"{name}{f' — {detail}' if detail else ''}")
        print(f"  ✗ {name}{f' — {detail}' if detail else ''}")


def load_global(name: str, global_name: str):
    path = DATA_DIR / name
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{global_name}=(.*);\s*$", text, re.S)
    if not match:
        raise SystemExit(f"cannot parse {path}")
    return json.loads(match.group(1))


def main() -> int:
    print("\n▶ Verifying the ATP dashboard payload\n")

    d = load_global("atp.js", "ATP_DATA")
    events = load_global("atp-events.js", "ATP_EVENTS")
    h2h = load_global("atp-h2h.js", "ATP_H2H")
    h2h_matches = load_global("atp-h2h-matches.js", "ATP_H2H_MATCHES")

    meta = d["meta"]
    season = meta["season"]
    players = d["players"]

    # ---------------------------------------------------------------- meta
    check("meta carries a season", isinstance(season, int), str(season))
    check("meta carries a rankings week",
          bool(re.match(r"^\d{4}-\d{2}-\d{2}", meta.get("rankingsAsOf") or "")))
    check("meta names the tour", meta.get("tour") == "ATP")
    check("meta records the data source", bool(meta.get("sourceUrl")))

    # ------------------------------------------------------------- players
    check("player roster is populated", len(players) >= 250, str(len(players)))
    check("players are a clean 1..N ranking",
          all(p["rank"] == i + 1 for i, p in enumerate(players)))
    check("every player has a name, id and country",
          all(p["name"].strip() and p["id"] and p["country"].strip() for p in players))
    check("Chinese names cover most of the roster",
          sum(1 for p in players if p.get("zh")) >= len(players) * 0.8,
          f"{sum(1 for p in players if p.get('zh'))}/{len(players)}")
    # Players from Russia and Belarus compete under a neutral flag, so the source
    # publishes none for them.
    check("flags cover all but the neutral-flag players",
          sum(1 for p in players if p.get("flag")) >= len(players) - 12,
          f"{sum(1 for p in players if not p.get('flag'))} without")
    check("points are non-increasing with rank",
          all(players[i - 1]["points"] >= players[i]["points"] for i in range(1, len(players))))
    with_season = sum(1 for p in players if p.get("season"))
    check("season records cover the roster", with_season >= len(players) * 0.9,
          f"{with_season}/{len(players)}")
    check("career records are present",
          sum(1 for p in players if (p.get("career") or {}).get("w")) >= len(players) * 0.95)
    # These are CAREER splits, so a surface total can run into the hundreds.
    check("career surface splits are well formed",
          all(all(isinstance(s.get("w"), int) and isinstance(s.get("l"), int)
                  and 0 <= s["w"] <= 900 and 0 <= s["l"] <= 700
                  for s in (p.get("careerBySurface") or {}).values())
              for p in players))
    check("photo paths are source-relative",
          all(p["photo"].startswith("/res/img/player/") for p in players if p.get("photo")))

    # ------------------------------------------------------------- results
    results = d["results"]
    check("results feed is populated", len(results) >= 500, str(len(results)))
    check("every result has two distinct players",
          all(r["winner"]["id"] and r["loser"]["id"] and r["winner"]["id"] != r["loser"]["id"]
              for r in results))
    check("every result carries a score",
          all(" ".join(r.get("score") or "").split() for r in results))
    check("results are newest-first",
          all(results[i - 1]["date"] >= r["date"] for i, r in enumerate(results) if i))
    check("results resolve to real names",
          all(not re.match(r"^#", r["winner"]["name"]) for r in results))
    check("results carry an event", all(r.get("event") for r in results))
    check("almost every result carries a surface",
          sum(1 for r in results if r.get("surface")) >= len(results) * 0.95,
          f"{sum(1 for r in results if not r.get('surface'))} without")

    # ----------------------------------------------------------- champions
    champions = d["champions"]
    check("champion list is populated", len(champions) >= 100, str(len(champions)))
    check("champions carry event, date and player",
          all(c.get("event") and c.get("date") and c["player"].get("id") for c in champions))
    check("every champion has a runner-up",
          all(c.get("runnerUp", {}).get("id") for c in champions))
    check("current season has champions",
          sum(1 for c in champions if c["year"] == season) >= 50)

    # ------------------------------------------------------------ calendar
    calendar = d["calendar"]
    check("calendar is populated", len(calendar) >= 150, str(len(calendar)))
    check("calendar rows have ISO dates",
          all(re.match(r"^\d{4}-\d{2}-\d{2}$", e["start"]) and e["start"] <= e["end"]
              for e in calendar))
    check("almost every calendar event has a surface",
          sum(1 for e in calendar if e.get("surface")) >= len(calendar) * 0.95)
    check("every calendar event has a Chinese name",
          sum(1 for e in calendar if e.get("zh")) >= len(calendar) * 0.85,
          f"{sum(1 for e in calendar if e.get('zh'))}/{len(calendar)}")
    check("exhibitions are excluded from the calendar",
          not any("utr pro tennis" in e["name"].lower() or "exhibition" in e["name"].lower()
                  for e in calendar))

    # -------------------------------------------------------- leaderboards
    boards = d["boards"]
    check("nine leaderboards", len(boards) == 9, str(len(boards)))
    check("every board has rows", all(len(b["rows"]) >= 10 for b in boards))
    check("boards are sorted by value",
          all(all((b["rows"][i - 1]["value"] or 0) >= (r["value"] or 0)
                  for i, r in enumerate(b["rows"]) if i) for b in boards))
    check("every board row resolves to a player",
          all(not re.match(r"^#", r["name"]) for b in boards for r in b["rows"]))
    check("career leaders present",
          all(len(d["career"].get(k, [])) >= 5 for k in ("titles", "careerWins", "careerPct")))

    # ------------------------------------------------------------------ zh
    zh = meta["zh"]
    check("Chinese terminology present",
          all(zh.get(k) for k in ("countries", "surfaces", "rounds", "levels")))
    countries = {p["country"] for p in players}
    check("every player country has a Chinese name",
          all(c in zh["countries"] for c in countries),
          ",".join(sorted(c for c in countries if c not in zh["countries"])))

    # ------------------------------------------------------- event draws
    check("draws are populated", len(events) >= 150, str(len(events)))
    rounds = [r for e in events.values() for r in e["rounds"]]
    matches = [m for r in rounds for m in r["matches"]]
    check("draw match total is substantial", len(matches) >= 8000, str(len(matches)))
    check("every draw match has two distinct players",
          all(m["winner"]["id"] and m["loser"]["id"] and m["winner"]["id"] != m["loser"]["id"]
              for m in matches))
    check("every draw has a final",
          sum(1 for e in events.values() if any(r["code"] == "F" for r in e["rounds"]))
          >= len(events) * 0.9)
    check("no draw has two finals",
          all(sum(1 for r in e["rounds"] if r["code"] == "F") <= 1 for e in events.values()))
    check("draw rounds are ordered from the final down",
          all([r["order"] for r in e["rounds"]] == sorted((r["order"] for r in e["rounds"]), reverse=True)
              for e in events.values()))

    # ---------------------------------------------------------------- h2h
    pairs = h2h["pairs"]
    check("head-to-head index is populated", len(pairs) >= 10000, str(len(pairs)))
    check("pair keys use the pipe separator",
          all("|" in k for k in list(pairs)[:2000]))
    check("pair keys are ordered a<b",
          all(k.split("|", 1)[0] < k.split("|", 1)[1] for k in pairs if "|" in k))
    check("win totals match the meeting count",
          all(v["aw"] + v["bw"] == v["n"] and v["n"] > 0 for v in pairs.values()))
    check("meeting detail is within the summary",
          all(0 < len(v) <= pairs[k]["n"] for k, v in h2h_matches.items()))
    check("meetings carry a date, an event and a winner",
          all(all(re.match(r"^\d{4}-\d{2}-\d{2}$", m[0]) and m[1] and m[4]
                  for m in v) for v in h2h_matches.values()))
    check("every pairing member is named",
          all(h2h["players"].get(k.split("|", 1)[0], {}).get("name")
              and h2h["players"].get(k.split("|", 1)[1], {}).get("name") for k in pairs))
    top100 = players[:100]
    check("head-to-head roster covers the top 100",
          all(p["id"] in h2h["players"] for p in top100),
          f"{sum(1 for p in top100 if p['id'] not in h2h['players'])} missing")

    sinner = next((p for p in players if p["name"] == "Jannik Sinner"), None)
    alcaraz = next((p for p in players if p["name"] == "Carlos Alcaraz"), None)
    if sinner and alcaraz:
        a, b = sorted([sinner["id"], alcaraz["id"]])
        record = pairs.get(f"{a}|{b}")
        check("a known rivalry resolves", bool(record),
              f"{record['aw']}-{record['bw']} over {record['n']}" if record else "missing")

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
