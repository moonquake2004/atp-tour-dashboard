#!/usr/bin/env python3
"""
Build the Chinese localisation snapshot for the ATP dashboard.

Sources
  · Player names  — Wikidata property P536 (ATP player id), matched to the feed's
                    full names, then normalised to Simplified Chinese through the
                    MediaWiki variant converter.
  · Countries     — curated table (the feed prints full country names).
  · Tournaments   — curated table for tour-level events, plus a city table that
                    rebuilds "<city> challenger" names.
  · Rounds/surfaces/levels — curated.

The daily results listing abbreviates surnames ("Sinner J."), which cannot be
matched to Wikidata, so Chinese names cover the ranking table and the player
profiles; abbreviated names in result rows stay in English.

    python3 pyscripts/fetch_zh.py
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import atp_terms
from wtalib import log, read_json, write_json
from zh_terms import VARIANT_CACHE, has_cjk, sparql, to_simplified


def name_key(value: str) -> frozenset:
    """
    A comparison key that survives every spelling difference between the two
    sources.

    The feed orders names by surname and may run a compound surname together
    ("Aliassime Felix Auger"), while Wikidata uses the natural order with accents
    and hyphens ("Félix Auger-Aliassime"), and particles vary in case
    ("de Minaur" / "De Minaur").  Comparing the SET of folded tokens ignores
    order, accents, hyphens and case at once.
    """
    import re
    import unicodedata

    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return frozenset(t for t in tokens if t)


def wikidata_players() -> dict[str, str]:
    """English name → Chinese label, for every player Wikidata indexes by ATP id."""
    query = """SELECT ?atpId ?en ?zh ?zhHans ?zhCn ?zhSg WHERE {
      ?p wdt:P536 ?atpId .
      OPTIONAL { ?p rdfs:label ?en . FILTER(lang(?en)="en") }
      OPTIONAL { ?p rdfs:label ?zh . FILTER(lang(?zh)="zh") }
      OPTIONAL { ?p rdfs:label ?zhHans . FILTER(lang(?zhHans)="zh-hans") }
      OPTIONAL { ?p rdfs:label ?zhCn . FILTER(lang(?zhCn)="zh-cn") }
      OPTIONAL { ?p rdfs:label ?zhSg . FILTER(lang(?zhSg)="zh-sg") }
    }"""
    rows = sparql(query)
    by_id: dict[str, dict] = {}
    for row in rows:
        atp_id = (row.get("atpId") or {}).get("value")
        if not atp_id:
            continue
        label = (
            (row.get("zhHans") or {}).get("value")
            or (row.get("zhCn") or {}).get("value")
            or (row.get("zhSg") or {}).get("value")
            or (row.get("zh") or {}).get("value")
            or ""
        )
        entry = by_id.setdefault(atp_id, {"zh": "", "en": ""})
        if label and not entry["zh"]:
            entry["zh"] = label
        english = (row.get("en") or {}).get("value")
        if english and not entry["en"]:
            entry["en"] = english

    log("zh", f"  Wikidata: {len(by_id)} ATP-indexed players")
    return {v["en"]: v["zh"] for v in by_id.values() if v["en"] and v["zh"]}


def wikidata_cities(names: list[str]) -> dict[str, str]:
    """
    Chinese labels for host cities, looked up by English name.

    Challenger events are named after their host city, and there are far more of
    them than are worth curating by hand, so their Chinese names come from
    Wikidata instead.  Only items that are actually cities are accepted, which
    keeps an event name from matching an unrelated article.
    """
    if not names:
        return {}
    out: dict[str, str] = {}
    chunk = 60
    for start in range(0, len(names), chunk):
        batch = names[start:start + chunk]
        values = " ".join('"' + n.title().replace('"', "").replace("\\", "") + '"@en' for n in batch)
        query = f"""SELECT ?name ?zh WHERE {{
          VALUES ?name {{ {values} }}
          ?item rdfs:label ?name .
          ?item rdfs:label ?zh . FILTER(lang(?zh)="zh")
          ?item wdt:P31/wdt:P279* wd:Q515 .
        }}"""
        try:
            for row in sparql(query):
                name = (row.get("name") or {}).get("value")
                label = (row.get("zh") or {}).get("value")
                if name and label:
                    out.setdefault(name.lower(), label)
        except RuntimeError as err:
            log("zh", f"  ! city lookup failed: {err}")
    return out


def _build() -> int:
    log("zh", "Building the Chinese localisation snapshot…")

    bios = read_json("bios.json", {}) or {}
    rankings = read_json("rankings-singles.json", {"players": []})
    tournaments = read_json("tournaments.json", {}) or {}
    calendar_events = (read_json("calendar.json", {}) or {}).get("events") or []
    names = read_json("h2h-names.json", {}) or {}

    # ------------------------------------------------------------- players
    wanted: dict[str, str] = {}
    for player in rankings["players"]:
        wanted[player["id"]] = player["name"]
    for pid, bio in bios.items():
        wanted.setdefault(pid, bio.get("name", ""))

    log("zh", f"  {len(wanted)} ranked players need a Chinese name")
    by_english = wikidata_players()

    # Index Wikidata by token set so name order and spelling do not matter.
    by_tokens: dict[frozenset, str] = {}
    for candidate, value in by_english.items():
        by_tokens.setdefault(name_key(candidate), value)
    log("zh", f"  Wikidata indexed into {len(by_tokens)} distinct name keys")

    raw: list[str] = []
    matched: dict[str, str] = {}
    curated = 0
    for pid, english in wanted.items():
        label = by_english.get(english) or by_tokens.get(name_key(english))
        if not label:
            label = atp_terms.player_zh(english)
            if label:
                curated += 1
        if label:
            matched[pid] = label
            raw.append(label)

    # ------------------------------------------------------- tournaments
    # Both the results crawl and the calendar page contribute event names, and
    # they abbreviate differently ("Szczecin chall." vs "Szczecin challenger"),
    # so both sets are resolved.
    tournament_map: dict[str, str] = {}
    uncovered: list[str] = []
    wanted_names: list[str] = [e["name"] for e in tournaments.values()]
    wanted_names += [e["name"] for e in calendar_events]
    for name in dict.fromkeys(wanted_names):
        zh = atp_terms.tournament_zh(name)
        if zh:
            tournament_map[name] = zh
            raw.append(zh)
        else:
            tournament_map[name] = ""
            uncovered.append(name)

    # ------------------------------------------------ simplified conversion
    unique = list(dict.fromkeys(raw))
    log("zh", f"  Converting {len(unique)} labels to Simplified Chinese…")
    converted = to_simplified(unique, cache_file=VARIANT_CACHE)

    def hans(value: str) -> str:
        return converted.get(value, value) if value else value

    players_final: dict[str, str] = {}
    latin_only = 0
    for pid, label in matched.items():
        value = hans(label)
        # A "Chinese" label that is really the Latin name would print the name
        # twice, so it is discarded.
        if not has_cjk(value):
            latin_only += 1
            continue
        players_final[pid] = value

    tournaments_final = {k: hans(v) for k, v in tournament_map.items()}

    # ------------------------------------------------------- host cities
    city_needed: dict[str, list[str]] = {}
    for name, zh in tournaments_final.items():
        if zh or "challenger" not in name.lower():
            continue
        city = re.sub(r"\s*(challenger|chall\.)\s*$", "", name.lower()).strip()
        city = re.sub(r"\s+\d+$", "", city).strip()
        if city and city not in atp_terms.CITY_ZH:
            city_needed.setdefault(city, []).append(name)

    if city_needed:
        log("zh", f"  Looking up {len(city_needed)} challenger host cities on Wikidata…")
        found = wikidata_cities(sorted(city_needed))
        log("zh", f"  Wikidata resolved {len(found)} of them")
        for city, events in city_needed.items():
            label = found.get(city)
            if not label:
                continue
            zh_city = hans(label)
            if not has_cjk(zh_city):
                continue
            for event in events:
                # Keep any numbering suffix so "Bogota 5" stays distinct.
                number = re.search(r"(\d+)\s*challenger$", event.lower())
                suffix = f" {number.group(1)}" if number else ""
                tournaments_final[event] = f"{zh_city}{suffix}挑战赛"

    tournaments_final = {k: v for k, v in tournaments_final.items()}
    countries_final = {k: v for k, v in atp_terms.COUNTRY_ZH.items()}

    # Challenger host cities the curated table does not yet know keep their
    # English name rather than showing a guess.
    tournaments_final = {k: v for k, v in tournaments_final.items()}

    if latin_only:
        log("zh", f'  discarded {latin_only} Latin-only "Chinese" label(s)')

    write_json("data/zh.json", {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "sources": {
            "playerNames": "Wikidata (property P536 — ATP player id)",
            "simplified": "MediaWiki zh-hans variant conversion",
            "terminology": "Curated ATP terminology",
        },
        "players": players_final,
        "tournaments": tournaments_final,
        "countries": countries_final,
        "rounds": atp_terms.ROUND_ZH,
        "surfaces": atp_terms.SURFACE_ZH,
        "levels": atp_terms.LEVEL_ZH,
    })

    covered = sum(1 for p in rankings["players"] if p["id"] in players_final)
    if curated:
        log("zh", f"  {curated} name(s) came from the curated transliteration table")
    log("zh", f"Done — {covered}/{len(rankings['players'])} ranked players have a Chinese name, "
              f"{sum(1 for v in tournaments_final.values() if v)}/{len(tournaments_final)} tournaments, "
              f"{len(countries_final)} countries.")
    if uncovered:
        log("zh", f"  {len(uncovered)} events without a curated Chinese name (English is shown): "
                  f"{', '.join(sorted(uncovered)[:5])}…")
    return 0


def main() -> int:
    """Build the zh snapshot, falling back to the stored copy when offline."""
    try:
        return _build()
    except Exception as err:  # noqa: BLE001 — Wikidata / variant converter unavailable
        cached = read_json("zh.json", None) or {}
        if not cached:
            raise
        log("zh", f"network unavailable ({err}) — keeping existing zh.json")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
