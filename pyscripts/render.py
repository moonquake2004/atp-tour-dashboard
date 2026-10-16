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
import os
import re
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


def format_score(value) -> str:
    """
    Normalise a stored score into standard tennis notation.

    Accepts the shapes the pipeline produces:
      · a plain string            -> returned as-is
      · a list of strings         -> joined with spaces ("6 3" -> "6 3")
      · a list of dicts           -> each dict is {"g": games, "tb": tiebreak},
                                     rendered as "7-6(5)"
      · missing/empty             -> "—"
    The parser layer already pairs per-set games into "6-7(5)" strings, so this
    function mostly guards against older snapshot shapes.
    """
    if value is None:
        return "—"
    if isinstance(value, str):
        return value if value.strip() else "—"
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            if isinstance(item, dict):
                g = item.get("g")
                tb = item.get("tb")
                s = str(g) if g is not None else ""
                if tb:
                    s = f"{s}({tb})"
                parts.append(s)
            else:
                parts.append(str(item))
        joined = " ".join(p for p in parts if p)
        return joined if joined else "—"
    s = str(value)
    return s if s.strip() else "—"


# ---------------------------------------------------------------------------
# Localised avatars
# ---------------------------------------------------------------------------

_AVATAR_DIR: str | None = None


def _set_avatar_dir(path) -> None:
    """Point the avatar renderer at the build's docs/assets/avatars directory."""
    global _AVATAR_DIR
    _AVATAR_DIR = str(path) if path else None


def _local_avatar(remote_path: str) -> str:
    """The site-local copy of a remote portrait, if the build downloaded one.

    The returned value is a site-relative URL (``assets/avatars/<name>``), not a
    filesystem path: pages are served from the repository root, so absolute local
    paths would break every deployed image.
    """
    if not _AVATAR_DIR or not remote_path:
        return ""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", remote_path.rsplit("/", 1)[-1])
    candidate = os.path.join(_AVATAR_DIR, name)
    if os.path.exists(candidate):
        return f"assets/avatars/{name}"
    return ""


# ---------------------------------------------------------------------------
# Static SVG helpers (pre-rendered, no client-side charting library)
# ---------------------------------------------------------------------------


def _num(value):
    """A numeric cell that can be compared, or None when absent."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _winrate(p: dict) -> float | None:
    career = p.get("career") or {}
    w, l = career.get("w"), career.get("l")
    if w is None or l is None or not (w + l):
        return None
    return round(100.0 * w / (w + l), 1)


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

        Tennis Explorer hosts player photos under /res/img/player/.  During the
        build the portraits are downloaded into docs/assets/avatars; when a local
        copy exists it is served from the site itself so the dashboard no longer
        depends on the upstream hotlink.  Players without a photo (local or
        remote) fall back to the CSS monogram layer behind the image.
        """
        path = (player or {}).get("photo") if isinstance(player, dict) else None
        if not path:
            entry = self.h2h_players.get(str(player if not isinstance(player, dict) else player.get("id")))
            path = (entry or {}).get("photo") or (entry or {}).get("p")
        if not path:
            return ""
        local = _local_avatar(path)
        if local:
            return local
        return path if path.startswith("http") else f"https://www.tennisexplorer.com{path}"

    def avatar(self, player, size: int = 34, cls: str = "") -> str:
        """
        Official headshot.

        The fallback is pure CSS — a monogram on a court-green disc behind the
        image — so a missing photo never leaves a broken icon.  If the remote
        portrait fails to load, the one-line onerror handler hides the broken
        image and reveals that same monogram, which is always present underneath.
        """
        initials = "".join(w[:1] for w in str(player.get("name") or "?").split()[:2]).upper()
        src = self.photo(player)
        img = ""
        if src:
            # Only emit the image when there is one: an empty src makes the browser
            # request the page itself as an image, which shows up as a failed load.
            # `onerror` hides the broken img so the CSS monogram beneath shows.
            img = (f'<img class="{esc(cls)}" src="{esc(src)}" alt="" loading="lazy" '
                   f'width="{size}" height="{size}" '
                   'onerror="this.onerror=null;this.style.display=\'none\'">')
        return (f'<span class="av" style="--av:{size}px">'
                f'<span class="av-mono" aria-hidden="true">{esc(initials)}</span>'
                f'{img}</span>')

    def trend_svg(self, player: dict, width: int = 560, height: int = 210) -> str:
        """
        A static SVG "career trend" panel: yearly main-tour titles as bars.

        The ATP snapshot carries no week-by-week ranking history, so the honest
        history we have is titles per season — plotted rather than invented.
        """
        by_year = (player.get("titles") or {}).get("byYear") or []
        data = sorted([t for t in by_year if (t.get("main") or 0) > 0],
                      key=lambda t: t["year"])[-10:]
        if not data:
            return ""
        max_v = max(t["main"] for t in data) or 1
        pad_l, pad_r, pad_t, pad_b = 8, 8, 22, 30
        slot = (width - pad_l - pad_r) / len(data)
        bars = []
        for i, t in enumerate(data):
            v = t["main"]
            bh = (height - pad_t - pad_b) * (v / max_v)
            x = pad_l + i * slot + slot * 0.22
            bw = slot * 0.56
            y = height - pad_b - bh
            bars.append(
                f'<g><rect class="trend-bar" x="{x:.1f}" y="{y:.1f}" '
                f'width="{bw:.1f}" height="{bh:.1f}" rx="2"/>'
                f'<text class="trend-tx" x="{x + bw / 2:.1f}" y="{y - 4:.1f}" '
                f'text-anchor="middle">{v}</text>'
                f'<text class="trend-tx2" x="{x + bw / 2:.1f}" y="{height - 8:.1f}" '
                f'text-anchor="middle">{t["year"]}</text></g>'
            )
        axis = (f'<line class="trend-ax" x1="{pad_l:.1f}" y1="{height - pad_b:.1f}" '
                f'x2="{width - pad_r:.1f}" y2="{height - pad_b:.1f}"/>')
        return (f'<svg class="trend-box" viewBox="0 0 {width} {height}" role="img" '
                f'aria-label="Titles per season">{axis}{"".join(bars)}</svg>')

    def compare_svg(self, a: dict, b: dict, width: int = 640, height: int = 244) -> str:
        """
        A static SVG symmetric bar chart for the player comparison panel.

        Each dimension is drawn as two halves: A grows left from the centre and
        B grows right.  Rank is inverted (lower is better); win rate and titles
        are scaled to the pair's best value.
        """
        dims = [
            ("排名", "Rank", _num(a.get("rank")), _num(b.get("rank")), True),
            ("积分", "Points", _num(a.get("points")), _num(b.get("points")), False),
            ("赛季胜场", "Season W", _num((a.get("season") or {}).get("w")),
             _num((b.get("season") or {}).get("w")), False),
            ("生涯冠军", "Titles", _num((a.get("titles") or {}).get("main")),
             _num((b.get("titles") or {}).get("main")), False),
            ("生涯胜场", "Career W", _num((a.get("career") or {}).get("w")),
             _num((b.get("career") or {}).get("w")), False),
            ("胜率", "Win %", _winrate(a), _winrate(b), False),
        ]
        mid = width / 2
        row_h = (height - 24) / len(dims)
        half = (width - 240) / 2
        rows = []
        for i, (zh, en, av, bv, invert) in enumerate(dims):
            y = 22 + i * row_h
            max_v = max(av or 0, bv or 0) or 1
            if invert:
                a_ratio = (max_v - (av or max_v)) / max_v if av else 0
                b_ratio = (max_v - (bv or max_v)) / max_v if bv else 0
            else:
                a_ratio = (av or 0) / max_v
                b_ratio = (bv or 0) / max_v
            a_w = half * max(0.0, a_ratio)
            b_w = half * max(0.0, b_ratio)
            rows.append(
                f'<g>'
                f'<text class="cmp-lbl" x="{mid:.1f}" y="{y + 8:.1f}" text-anchor="middle">'
                f'<tspan>{esc(zh)}</tspan>'
                f'<tspan class="cmp-lbl-en" dx="4">{esc(en)}</tspan></text>'
                f'<rect class="cmp-bar-a" x="{mid - a_w:.1f}" y="{y:.1f}" '
                f'width="{a_w:.1f}" height="12" rx="2"/>'
                f'<rect class="cmp-bar-b" x="{mid:.1f}" y="{y:.1f}" '
                f'width="{b_w:.1f}" height="12" rx="2"/>'
                f'<text class="cmp-val" x="{mid - a_w - 6:.1f}" y="{y + 10:.1f}" '
                f'text-anchor="end">{esc(num(av))}</text>'
                f'<text class="cmp-val" x="{mid + b_w + 6:.1f}" y="{y + 10:.1f}">'
                f'{esc(num(bv))}</text>'
                f'</g>'
            )
        ha = esc((a.get("zh") or a.get("name") or ""))[:14]
        hb = esc((b.get("zh") or b.get("name") or ""))[:14]
        head = (f'<text class="cmp-name-a" x="{mid - 60:.1f}" y="12" text-anchor="end">{ha}</text>'
                f'<text class="cmp-name-b" x="{mid + 60:.1f}" y="12">{hb}</text>')
        return (f'<svg class="cmp-svg" viewBox="0 0 {width} {height}" role="img" '
                f'aria-label="Player comparison">{head}{"".join(rows)}</svg>')
