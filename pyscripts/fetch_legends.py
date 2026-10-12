#!/usr/bin/env python3
"""
Fetch career records for retired champions.

The career boards had been limited to players inside the current ranking table,
which left them reading as "active title leaders" — Djokovic's 101 at the top
while Connors' 109, Lendl's 94 and Sampras' 64 were nowhere.  This step adds the
retired greats so the board actually answers "who has won the most".

Slugs are not guessable: `borg` resolves to Sofie Borg and `wawrinka` to a
different Wawrinka, so every candidate is discovered from the tournament archive
draws — where the source itself links the real profile — and then confirmed by
parsing the page.  A candidate is kept only when its parsed main-tour title count
clears the threshold, so a namesake can never slip in.

    python3 pyscripts/fetch_legends.py
"""

from __future__ import annotations

from datetime import datetime, timezone

import re

import te
from wtalib import env_int, log, read_json, write_json

MIN_TITLES = env_int("ATP_LEGEND_MIN_TITLES", 15)

# Archive draws to harvest player slugs from.  Coverage reaches back to the
# mid-1990s, which is where the modern-era greats still appear.
ARCHIVE_SLAMS = ["wimbledon", "us-open", "australian-open", "french-open"]
ARCHIVE_YEARS = [1995, 1998, 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014,
                 2016, 2018, 2020, 2022, 2024]

# Surname → the legend it must resolve to.  The surname alone is ambiguous, so the
# full name is checked against the page before a record is kept.
LEGEND_NAMES = {
    "federer": "Roger Federer",
    "nadal": "Rafael Nadal",
    "sampras": "Pete Sampras",
    "agassi": "Andre Agassi",
    "hewitt": "Lleyton Hewitt",
    "safin": "Marat Safin",
    "roddick": "Andy Roddick",
    "ferrero": "Juan Carlos Ferrero",
    "moya": "Carlos Moya",
    "kuerten": "Gustavo Kuerten",
    "kafelnikov": "Yevgeny Kafelnikov",
    "rios": "Marcelo Rios",
    "muster": "Thomas Muster",
    "courier": "Jim Courier",
    "ivanisevic": "Goran Ivanisevic",
    "murray": "Andy Murray",
    "ferrer": "David Ferrer",
    "davydenko": "Nikolay Davydenko",
    "tsonga": "Jo-Wilfried Tsonga",
    "del-potro": "Juan Martin del Potro",
    "wawrinka": "Stan Wawrinka",
    "becker": "Boris Becker",
    "edberg": "Stefan Edberg",
    "bjorkman": "Jonas Bjorkman",
    "nalbandian": "David Nalbandian",
    "grosjean": "Sebastien Grosjean",
    "haas": "Tommy Haas",
    "kohlschreiber": "Philipp Kohlschreiber",
    "lopez": "Feliciano Lopez",
    "verdasco": "Fernando Verdasco",
    "baghdatis": "Marcos Baghdatis",
    "blake": "James Blake",
    "ginepri": "Robby Ginepri",
    "fish": "Mardy Fish",
    "mathieu": "Paul-Henri Mathieu",
    "monfils": "Gael Monfils",
    "simon": "Gilles Simon",
    "benneteau": "Julien Benneteau",
    "llodra": "Michael Llodra",
    "steps": "",
}


def harvest_slugs() -> dict[str, str]:
    """slug → the name the archive draw printed next to it."""
    found: dict[str, str] = {}
    for year in ARCHIVE_YEARS:
        for slam in ARCHIVE_SLAMS:
            doc = te.get(f"/{slam}/{year}/atp-men/")
            if not doc:
                continue
            for match in te.PLAYER_LINK.finditer(doc):
                slug = match.group(2).rstrip("/")
                label = te.text(match.group(3))
                if slug and label:
                    found.setdefault(slug, label)
        log("legends", f"  archive {year}: {len(found)} distinct player slugs so far")
    return found


def surname_of(slug: str) -> str:
    return slug.split("-")[0].lower()


def main() -> int:
    log("legends", "Building the retired-champions snapshot…")

    existing = read_json("legends.json", {}) or {}

    log("legends", "  Harvesting profile slugs from the tournament archive…")
    slugs = harvest_slugs()
    log("legends", f"  {len(slugs)} slugs harvested")

    # Candidate slugs whose surname matches a wanted legend.
    candidates: dict[str, str] = {}   # slug -> expected full name
    for slug in slugs:
        surname = surname_of(slug)
        expected = LEGEND_NAMES.get(surname)
        if expected:
            candidates[slug] = expected
    log("legends", f"  {len(candidates)} candidates match a wanted surname")

    ranked = read_json("rankings-singles.json", {"players": []})
    active_ids = {p["id"] for p in ranked["players"]}

    out: dict = dict(existing)
    kept, rejected = 0, 0

    for slug, expected in sorted(candidates.items()):
        if slug in active_ids:
            continue
        doc = te.get(te.PLAYER_BASE.format(slug=slug))
        detail = te.parse_player_detail(doc)
        if not detail:
            rejected += 1
            continue

        # The page must be the legend we asked for, not a namesake.  The parsed
        # profile carries no name, so the identity comes from the page title.
        page_name = te.page_name(doc)
        expected_tokens = [t for t in re.split(r"\s+", expected.lower()) if len(t) > 1]
        if not page_name or not all(t in page_name.lower() for t in expected_tokens[-2:]):
            rejected += 1
            continue

        titles = te.parse_player_titles(doc)
        main = sum(t.get("main", 0) for t in titles)
        if main < MIN_TITLES:
            rejected += 1
            continue

        balance = te.parse_player_balance(doc)
        out[slug] = {
            "id": slug,
            "slug": slug,
            "name": page_name or expected,
            "country": detail.get("country") or "",
            "flag": "",
            "rank": None,
            "points": None,
            "move": None,
            "retired": True,
            "age": detail.get("age"),
            "birth": detail.get("birth") or "",
            "height": detail.get("height"),
            "weight": detail.get("weight"),
            "hand": detail.get("hand") or "",
            "highRank": detail.get("highRank"),
            "highRankDoubles": detail.get("highRankDoubles"),
            "photo": detail.get("photo") or "",
            "career": (balance.get("career") or {}).get("total") or {},
            "careerBySurface": (balance.get("career") or {}).get("bySurface") or {},
            "seasons": balance.get("seasons") or {},
            "titles": titles,
            "titleCount": main,
        }
        kept += 1
        log("legends", f"  ✓ {slug:18} {out[slug]['name']:24} {main:3} titles")

    write_json("data/legends.json", {k: out[k] for k in sorted(out)})

    log("legends", f"Done — {len(out)} retired champions kept "
                   f"({kept} new, {rejected} candidacy rejected), threshold {MIN_TITLES} titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
