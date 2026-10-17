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
from datetime import date, timedelta

import te
from generate_data import EXHIBITION_MARKERS
from wtalib import env_int, log, read_json, write_json

WORKERS = env_int("ATP_EVENT_WORKERS", 2)
LIMIT = env_int("ATP_EVENT_LIMIT", 400)
# Draws captured while an event was still running are incomplete, and a stored
# draw was never re-fetched.  Anything that played inside this window is re-read
# so its later rounds (and the completed bracket) land once they exist.
RECENT_DAYS = env_int("ATP_EVENT_RECENT_DAYS", 10)


def main() -> int:
    tournaments = read_json("tournaments.json", {}) or {}
    if not tournaments:
        raise SystemExit("no tournaments — run fetch_results.py first")

    existing: dict = read_json("event-matches.json", {}) or {}
    # Only events that actually had matches are worth a page.  Exhibition series
    # are excluded: the site does not publish their pages, and their source pages
    # fail persistently, so crawling them only adds failed requests every run.
    wanted = [
        t for t in tournaments.values()
        if t.get("matches")
        and not any(m in (t.get("name") or "").lower() for m in EXHIBITION_MARKERS)
    ]
    wanted.sort(key=lambda t: (t["year"], t["dates"][0] if t.get("dates") else ""), reverse=True)
    wanted = wanted[:LIMIT]

    today = date.today().isoformat()
    recent_cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()

    def _needs_fetch(event: dict) -> bool:
        stored = existing.get(event["path"])
        if not stored:
            return True
        dates = event.get("dates") or []
        last = max(dates) if dates else ""
        if not last:
            return False
        rounds = {r.get("code") for r in stored.get("rounds") or []}
        # The event is over but the stored bracket never reached a final, which
        # means it was captured mid-tournament and its last rounds are missing.
        if last < today and "F" not in rounds:
            return True
        # Still in play, or finished so recently that rounds may still be landing.
        return last >= recent_cutoff

    todo = [t for t in wanted if _needs_fetch(t)]
    if not todo:
        log("events", f"Nothing to fetch — all {len(existing)} draws already stored and current.")
        return 0
    log("events", f"Fetching/freshening {len(todo)} draws "
                  f"({sum(1 for t in todo if t['path'] in existing)} refreshes)…")

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
