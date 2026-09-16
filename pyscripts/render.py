"""
Render the dashboard as pre-built HTML.

The site is generated, not rendered in the browser: every panel, player page and
event page is a complete HTML document produced here.  Interaction is CSS-driven,
so the site works with JavaScript switched off:

  · language      three anchors at the top of <body> (#lang-both/#lang-cn/#lang-en)
                  are siblings of the content, so :target toggles .cn/.en
  · modals        #player-<id> / #event-<id>-<year> targets reveal a fixed overlay
  · tables        sorting is pre-rendered as several sections, shown by :target
  · tabs          <details> elements, which open without script

Standard library only; the only dependency is the data the pipeline produced.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from wtalib import ROOT

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

MONTH = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

SURFACE_EN = {"HARD": "Hard", "CLAY": "Clay", "GRASS": "Grass",
              "CARPET": "Carpet", "INDOORS": "Indoors", "NOT SET": "Not set"}


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "—"


def pct(value, digits: int = 1) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def money(value) -> str:
    if not value:
        return "—"
    return f"${value:,.0f}"


def money_short(value) -> str:
    if not value:
        return "—"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M" if value < 10_000_000 else f"${value / 1_000_000:.0f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:,.0f}"


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return None


def short_date(value, with_year: bool = False) -> str:
    d = _parse_date(value)
    if not d:
        return "—"
    text = f"{d.day} {MONTH[d.month]}"
    return f"{text} {d.year}" if with_year else text


def iso_date(value) -> str:
    d = _parse_date(value)
    return d.strftime("%Y-%m-%d") if d else "—"


def timestamp(value=None) -> str:
    d = _parse_date(value) if value else None
    if d:
        return f"{d.day} {MONTH[d.month]} {d.year}"
    now = datetime.now(timezone.utc)
    return f"{now.day} {MONTH[now.month]} {now.year}"


# ---------------------------------------------------------------------------
# Bilingual primitives
# ---------------------------------------------------------------------------


def bi(zh, en="", cls: str = "", tag: str = "span") -> str:
    """
    Render a Chinese/English pair.

    Both languages live in the document; CSS picks which is shown, so switching
    language never re-renders anything.  Identical strings collapse to one line so
    a player or country without a translation is not printed twice.
    """
    c = ("" if zh is None else str(zh)).strip()
    e = ("" if en is None else str(en)).strip()
    klass = f' class="{cls}"' if cls else ""
    if not c or c == e:
        return f"<{tag}{klass}>{esc(e or c)}</{tag}>"
    if not e:
        return f"<{tag}{klass}>{esc(c)}</{tag}>"
    return (
        f'<{tag}{klass}><span class="cn">{esc(c)}</span>'
        f'<span class="en">{esc(e)}</span></{tag}>'
    )


class Context:
    """Everything the renderers need: the payload plus the Chinese lookup."""

    def __init__(self, data: dict, events: dict, h2h: dict):
        self.data = data
        self.meta = data.get("meta", {})
        self.players = data.get("players", [])
        self.results = data.get("results", [])
        self.champions = data.get("champions", [])
        self.calendar = data.get("calendar", [])
        self.digest = data.get("eventDigest", {})  # unused by ATP; kept for parity
        self.boards = data.get("boards", [])
        self.career = data.get("career", {})
        self.season_records = data.get("seasonRecords", {})  # fold-in for ATP
        self.tournament_zh = data.get("tournamentZh", {})
        self.zh = self.meta.get("zh", {})
        self.events = events
        self.h2h = h2h
        self.season = self.meta.get("season")
        self.by_id = {p["id"]: p for p in self.players}
        self.h2h_players = h2h.get("players", {})
        self.h2h_pairs = h2h.get("pairs", {})
        self.counts = self.meta.get("counts", {})
        self.stamp = (self.meta.get("generatedAt") or "")[:19]
        # Pairing pages are generated for the top N only; filled in by build_site
        # so every renderer can tell a real link from one that would 404.
        self.pair_ids: set[int] = set()
        self.pair_roster: list[dict] = []

    def has_pair_page(self, a: int, b: int) -> bool:
        return a in self.pair_ids and b in self.pair_ids

    # -- lookups ---------------------------------------------------------
    def player(self, pid) -> dict:
        """
        Resolve any player id to a record.

        ATP ids are short hashes ("8b8e8", "gurri"), not numbers, so the id is
        used as-is and only ever compared as a string.
        """
        key = str(pid)
        if key in self.by_id:
            return self.by_id[key]
        entry = self.h2h_players.get(key)
        if entry:
            # The generated roster uses long keys ("name"/"photo"); older snapshots
            # used short ones ("n"/"p").  Both are accepted.
            return {"id": key,
                    "name": entry.get("name") or entry.get("n") or "",
                    "zh": entry.get("zh", ""),
                    "country": entry.get("country") or entry.get("c") or "",
                    "flag": entry.get("flag") or entry.get("f") or "",
                    "rank": entry.get("rank") if entry.get("rank") is not None else entry.get("r"),
                    "photo": entry.get("photo") or entry.get("p") or ""}
        return {"id": key, "name": f"#{key}", "zh": "", "country": "", "rank": None}

    def name(self, player: dict | None, cls: str = "") -> str:
        """A player's name as a bilingual pair."""
        if not player:
            return ""
        return bi(player.get("zh") or player.get("name"), player.get("name"), cls)

    def player_link(self, player: dict | None, cls: str = "") -> str:
        if not player:
            return ""
        klass = f' class="{cls}"' if cls else ""
        return f'<a href="player-{player["id"]}.html"{klass}>{self.name(player)}</a>'

    def country(self, name) -> str:
        """ATP data carries full country names ("Italy"), not IOC codes."""
        raw = str(name or "").strip()
        if not raw:
            return ""
        return bi(self.zh.get("countries", {}).get(raw, ""), raw)

    def level(self, level) -> str:
        if not level:
            return ""
        return bi(self.zh.get("levels", {}).get(level, ""), level)

    def round_(self, code) -> str:
        c = str(code or "").upper()
        zh = self.zh.get("rounds", {}).get(c, "")
        return bi(zh, c) if zh else esc(c)

    def surface(self, surface) -> str:
        raw = str(surface or "").strip()
        table = self.zh.get("surfaces", {})
        # The table is keyed by the display form ("Hard"); match case-insensitively
        # so a feed that shouts "HARD" still resolves.
        zh = table.get(raw) or next((v for k, v in table.items() if k.lower() == raw.lower()), "")
        label = SURFACE_EN.get(raw.upper(), raw or "—")
        return bi(zh, label)

    def surface_chip(self, surface) -> str:
        key = str(surface or "").upper()
        label = SURFACE_EN.get(key, surface or "—")
        return f'<span class="sfc {esc(label.title())}"><i></i>{self.surface(surface)}</span>'

    def tournament(self, name) -> str:
        return bi(self.tournament_zh.get(name, ""), name)

    def level_tag(self, level) -> str:
        if not level:
            return ""
        text = str(level)
        lowered = text.lower()
        cls = ""
        if "grand slam" in lowered:
            cls = "gs"
        elif "finals" in lowered:
            cls = "finals"
        elif "challenger" in lowered:
            cls = "w250"
        elif "team" in lowered:
            cls = "w500"
        en = "SLAM" if lowered == "grand slam" else text
        return f'<span class="tag-lvl {cls}">{bi(self.zh.get("levels", {}).get(text, ""), en)}</span>'

    def move(self, value) -> str:
        v = int(value or 0)
        if not v:
            return '<span class="move flat">—</span>'
        if v > 0:
            return f'<span class="move up">▲ +{v}</span>'
        return f'<span class="move down">▼ −{abs(v)}</span>'

    def photo(self, player) -> str:
        """
        Portrait URL.

        Tennis Explorer hosts player photos under /res/img/player/; players
        without one fall back to the CSS monogram layer behind the image.
        """
        path = (player or {}).get("photo") if isinstance(player, dict) else None
        if not path:
            entry = self.h2h_players.get(str(player if not isinstance(player, dict) else player.get("id")))
            path = (entry or {}).get("photo") or (entry or {}).get("p")
        if not path:
            return ""
        return path if path.startswith("http") else f"https://www.tennisexplorer.com{path}"

    def avatar(self, player, size: int = 34, cls: str = "") -> str:
        """
        Official headshot.

        The fallback is pure CSS — a monogram on a court-green disc behind the
        image — so a missing photo never leaves a broken icon and no inline
        JavaScript is needed across the ~1,700 generated pages.
        """
        initials = "".join(w[:1] for w in str(player.get("name") or "?").split()[:2]).upper()
        return (
            f'<span class="av" style="--av:{size}px">'
            f'<span class="av-mono" aria-hidden="true">{esc(initials)}</span>'
            f'<img class="{esc(cls)}" src="{self.photo(player)}" alt="" loading="lazy" '
            f'width="{size}" height="{size}"></span>'
        )
