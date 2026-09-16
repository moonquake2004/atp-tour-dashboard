#!/usr/bin/env python3
"""
Fetch each event's complete singles draw.

The daily results crawl records who played whom, but not the round.  A
tournament's own page carries the full draw with round codes and titles
("1. round" … "final"), which is what the event pages need.

    python3 pyscripts/fetch_events.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import te
from wtalib import env_int, log, read_json, write_json

WORKERS = env_int("ATP_EVENT_WORKERS", 2)
LIMIT = env_int("ATP_EVENT_LIMIT", 400)


def main() -> int:
    tournaments = read_json("tournaments.json", {}) or {}
    if not tournaments:
        raise SystemExit("no tournaments — run fetch_results.py first")

    existing: dict = read_json("event-matches.json", {}) or {}
    # Only events that actually had matches are worth a page.
    wanted = [t for t in tournaments.values() if t.get("matches")]
    wanted.sort(key=lambda t: (t["year"], t["dates"][0] if t.get("dates") else ""), reverse=True)
    wanted = wanted[:LIMIT]

    todo = [t for t in wanted if t["path"] not in existing]
    if not todo:
        log("events", f"Nothing to fetch — all {len(existing)} draws already stored.")
        return 0
    log("events", f"Fetching draws for {len(todo)} events (resuming)…")

    failures = 0

    def handle(event: dict) -> None:
        doc = te.get(event["path"])
        draw = te.parse_event_draw(doc, event["year"])
        if not draw["rounds"]:
            raise RuntimeError("no draw found")
        # The event page is the only place the surface and prize money appear.
        meta = te.parse_event_meta(doc)
        total = sum(len(r["matches"]) for r in draw["rounds"].values())
        existing[event["path"]] = {
            "path": event["path"],
            "name": event["name"],
            "year": event["year"],
            "level": event.get("level") or "",
            "surface": meta.get("surface") or event.get("surface") or "",
            "prize": meta.get("prize"),
            "currency": meta.get("currency") or "",
            "country": meta.get("country") or "",
            "flag": event.get("flag") or "",
            "dates": event.get("dates") or [],
            "rounds": [
                {"code": code,
                 "label": rnd["label"],
                 "order": rnd["order"],
                 "title": rnd["title"],
                 "matches": rnd["matches"]}
                for code, rnd in draw["rounds"].items()
            ],
            "players": draw["players"],
            "total": total,
        }

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(handle, e): e for e in todo}
        done = 0
        for future in as_completed(futures):
            event = futures[future]
            try:
                future.result()
            except Exception as err:  # noqa: BLE001
                failures += 1
                print(f"  ! {event['name']} {event['year']}: {err}")
            done += 1
            if done % 20 == 0:
                log("events", f"{done}/{len(todo)}…")
                write_json("data/event-matches.json", {k: existing[k] for k in sorted(existing)})

    write_json("data/event-matches.json", {k: existing[k] for k in sorted(existing)})
    matches = sum(v["total"] for v in existing.values())
    log("events", f"Done — {len(existing)} draws, {matches} matches"
                  + (f", {failures} failures" if failures else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
