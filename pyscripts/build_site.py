#!/usr/bin/env python3
"""
Generate the publishable site into ``docs/``.

Everything is written as complete HTML — the panels, the player profiles and the
event draws — so the site works with JavaScript switched off.  The output contains
no <script> tag at all: language switching, the calendar's status filters, the
ranking sort orders and the head-to-head flow are all driven by CSS `:target`.

    python3 pyscripts/build_site.py
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pages
from generate_data import EXHIBITION_MARKERS
from render import Context
from wtalib import DATA_DIR, ROOT, log


def load_globals(name: str, global_name: str):
    """Read a generated data file, which is a script assigning one global."""
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"missing {path} — run generate_data.py first")
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"window\.{global_name}=(.*);\s*$", text, re.S)
    if not match:
        raise SystemExit(f"cannot parse {path}")
    return json.loads(match.group(1))


SEP = "|"


def _pair_key(a: str, b: str) -> str:
    """Index key; ids may contain a dash, so "|" separates the pair."""
    return f"{a}{SEP}{b}" if a < b else f"{b}{SEP}{a}"


def _pair_file(a: str, b: str) -> str:
    """Filename for a pairing; the separator becomes a dash as ids never do."""
    return f"h2h-{_pair_key(a, b).replace(SEP, '-')}.html"


def _recent_matches(daily: dict, tournaments: dict, pid: str, limit: int = 30) -> list[dict]:
    """
    A player's matches from the stored results, newest first.

    The daily crawl records every completed match, so this replaces a per-player
    match log — no extra fetching, and it covers players outside the ranking table
    as well.
    """
    out = []
    for day in sorted(daily, reverse=True):
        for match in daily[day]["matches"]:
            winner, loser = match.get("winner") or {}, match.get("loser") or {}
            if pid == winner.get("id"):
                opponent, won = loser, 1
            elif pid == loser.get("id"):
                opponent, won = winner, 0
            else:
                continue
            out.append({
                "d": day,
                "t": match["tournament"],
                "svc": (tournaments.get(match.get("tournamentPath") or "") or {}).get("surface") or "",
                "sc": " ".join(match.get("score") or []),
                "w": won,
                "oid": opponent.get("id") or "",
                "o": opponent.get("name") or "",
                "oc": "",
                "orank": None,
            })
            if len(out) >= limit:
                return out
    return out


def main() -> int:
    log("site", "Generating the static site…")

    data = load_globals("atp.js", "ATP_DATA")
    events = load_globals("atp-events.js", "ATP_EVENTS")
    h2h = load_globals("atp-h2h.js", "ATP_H2H")
    h2h_meetings = load_globals("atp-h2h-matches.js", "ATP_H2H_MATCHES")
    daily = json.loads((DATA_DIR / "results-daily.json").read_text(encoding="utf-8"))
    tournaments = json.loads((DATA_DIR / "tournaments.json").read_text(encoding="utf-8"))

    ctx = Context(data, events, h2h)
    # The top N by ranking, which is the range pairing pages are generated for.
    # Declared before anything renders so no link points at a page that will not
    # exist — the single definition of "in range" for the whole builder.
    pair_ids = {p["id"] for p in ctx.players[:pages.H2H_DEPTH]}
    ctx.pair_ids = pair_ids
    ctx.pair_roster = [p for p in ctx.players if p["id"] in pair_ids]

    out = ROOT / "docs"
    if out.exists():
        shutil.rmtree(out)
    src_assets = Path(__file__).resolve().parent.parent / "site-py" / "assets"
    if not src_assets.exists():
        raise SystemExit(f"missing {src_assets}")
    shutil.copytree(src_assets, out / "assets")
    # favicon.ico lives at the site root so that crawlers find it without reading
    # the markup; the per-size PNGs stay in assets/ alongside the touch icon.
    (out / "favicon.ico").write_bytes((src_assets / "favicon.ico").read_bytes())

    written = 0

    def write(name: str, html: str) -> None:
        nonlocal written
        (out / name).write_text(html, encoding="utf-8")
        written += 1

    # ------------------------------------------------------------ main panels
    write("index.html", pages.overview(ctx))
    write("calendar.html", pages.calendar(ctx))
    write("results.html", pages.results_page(ctx))
    write("rankings.html", pages.rankings(ctx))
    write("players.html", pages.players_page(ctx))
    write("stats.html", pages.stats_page(ctx))
    log("site", "  ✓ 6 panels")

    # --------------------------------------------------------- player profiles
    ranked = {p["id"] for p in ctx.players}
    rival_ids = [p["id"] for p in ctx.players[:30] if p["id"] in pair_ids]
    for player in ctx.players:
        pid = player["id"]
        rivals = []
        for other in rival_ids:
            if other == pid:
                continue
            record = ctx.h2h_pairs.get(_pair_key(pid, other))
            if not record:
                continue
            is_low = pid < other
            rivals.append({
                "id": other,
                "player": ctx.player(other),
                "wins": record["aw"] if is_low else record["bw"],
                "losses": record["bw"] if is_low else record["aw"],
            })
        rivals.sort(key=lambda r: (-(r["wins"] + r["losses"]), r["player"].get("rank") or 9999))
        write(f"player-{pid}.html",
              pages.player_page(ctx, player, rivals,
                                _recent_matches(daily, tournaments, pid)))
    log("site", f"  ✓ {len(ctx.players)} player profiles")

    # Every other player named anywhere gets a compact page, so no link 404s.
    extra = 0
    for pid, entry in ctx.h2h_players.items():
        if pid in ranked:
            continue
        write(f"player-{pid}.html", pages.player_page_light(ctx, entry))
        extra += 1
    log("site", f"  ✓ {extra} additional player pages")

    # Players who appear only in a draw (Davis Cup squads, qualifying entrants)
    # are absent from the head-to-head index, so they are collected from the draws
    # to keep every generated link resolvable.
    draw_only = 0
    for event in events.values():
        for pid, entry in (event.get("players") or {}).items():
            if pid in ranked or pid in ctx.h2h_players:
                continue
            if (out / f"player-{pid}.html").exists():
                continue
            ctx.h2h_players[pid] = {
                "id": pid, "name": entry.get("name", ""), "zh": "",
                "country": "", "flag": "", "rank": None, "photo": "",
            }
            write(f"player-{pid}.html", pages.player_page_light(ctx, ctx.h2h_players[pid]))
            draw_only += 1
    log("site", f"  ✓ {draw_only} draw-only player pages")

    # ------------------------------------------------------------- event pages
    # Exhibition and training series (the UTR sets most of all) are excluded from
    # the calendar, so their draw pages are not generated either: they would be
    # orphan documents of several hundred kilobytes each.
    event_pages = 0
    for event in events.values():
        if any(marker in event["name"].lower() for marker in EXHIBITION_MARKERS):
            continue
        slug = event["path"].strip("/").split("/")[0]
        write(f'event-{slug}-{event["year"]}.html', pages.event_page(ctx, event))
        event_pages += 1
    log("site", f"  ✓ {event_pages} event pages")

    # ---------------------------------------------------------- head-to-head
    roster = ctx.pair_roster
    write("h2h.html", pages.h2h_hub(ctx, roster))
    for player in roster:
        opponents = [o for o in roster if o["id"] != player["id"]]
        write(f'h2h-pick-{player["id"]}.html', pages.h2h_pick(ctx, player, opponents))
    pairs = 0
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            key = _pair_key(a["id"], b["id"])
            write(_pair_file(a["id"], b["id"]),
                  pages.h2h_pair(ctx, a, b, ctx.h2h_pairs.get(key), h2h_meetings.get(key, [])))
            pairs += 1
    log("site", f"  ✓ 1 hub + {len(roster)} pickers + {pairs} pairing pages")

    # -------------------------------------------------------------------- SEO
    (out / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        "Sitemap: https://moonquake2004.github.io/atp-tour-dashboard/sitemap.xml\n",
        encoding="utf-8",
    )
    # Full sitemap: the panels plus every page carrying unique content.  Compact
    # pages for players outside the ranking table are deliberately left out — they
    # are thin, and thousands of thin URLs dilute crawl priority for the rest.
    lastmod = (ctx.meta.get("generatedAt") or "")[:10]
    base_url = "https://moonquake2004.github.io/atp-tour-dashboard/"
    entries = {u: "weekly" for u in (
        "index.html", "rankings.html", "players.html", "calendar.html",
        "results.html", "stats.html", "h2h.html",
    )}
    for player in ctx.players:
        entries[f'player-{player["id"]}.html'] = "weekly"
    for event in events.values():
        if any(marker in event["name"].lower() for marker in EXHIBITION_MARKERS):
            continue
        slug = event["path"].strip("/").split("/")[0]
        entries[f'event-{slug}-{event["year"]}.html'] = "monthly"
    for player in roster:
        entries[f'h2h-pick-{player["id"]}.html'] = "weekly"
    for i, a in enumerate(roster):
        for b in roster[i + 1:]:
            low, high = min(a["id"], b["id"]), max(a["id"], b["id"])
            entries[f'h2h-{low}-{high}.html'] = "monthly"
    sitemap = "\n".join(
        f'  <url><loc>{base_url}{u}</loc><changefreq>{freq}</changefreq>'
        f'<lastmod>{lastmod}</lastmod></url>'
        for u, freq in entries.items()
    )
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{sitemap}\n</urlset>\n",
        encoding="utf-8",
    )

    (out / ".nojekyll").write_text("", encoding="utf-8")
    log("site", "  ✓ robots.txt · sitemap.xml · .nojekyll")

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    log("site", f"Done — {written} pages, {total / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
