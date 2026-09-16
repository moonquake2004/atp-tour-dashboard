"""
Tennis Explorer client and HTML parsers.

Tennis Explorer is the data source for this dashboard: it publishes current ATP
rankings, the tour calendar with complete draws, per-player match logs and
head-to-head records, and its robots.txt permits everything this pipeline reads
(it excludes only /redirect/, /terms-of-use/ and /contact/).

Unlike the WTA feed — an undocumented JSON API — these are server-rendered HTML
pages, so each page has a small parser here.  Parsers are written against the
markup's stable hooks (class names, the `title` attributes carrying full round
names) and are verified by the assertions in verify.py.

Standard library only: the HTML is walked with html.parser, never a DOM library.
"""

from __future__ import annotations

import html as html_module
import re
import threading
import time
import urllib.error
import urllib.parse
from html.parser import HTMLParser

from wtalib import SSL_CONTEXT, UA, log

BASE = "https://www.tennisexplorer.com"

# Tennis Explorer is a small site; keep the request rate low and serial.
MAX_CONCURRENCY = 2
MIN_GAP = 1.1

_gate = threading.Lock()
_slots = threading.Semaphore(MAX_CONCURRENCY)
_last = 0.0


def _throttle() -> None:
    global _last
    with _gate:
        now = time.monotonic()
        wait = _last + MIN_GAP - now
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _last = now


def get(path: str, *, retries: int = 4, timeout: float = 40.0) -> str:
    """Fetch a page and return its HTML, with politeness and backoff."""
    import http.client

    url = path if path.startswith("http") else BASE + path
    parsed = urllib.parse.urlsplit(url)
    target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "Referer": BASE + "/",
    }

    last_error: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(1.5 * attempt)
        with _slots:
            _throttle()
            # The server occasionally truncates a response mid-body.  curl handles
            # that far better than the Python stack, so after the second failure
            # the request is handed to it.
            if attempt >= 1:
                try:
                    return _curl(url, timeout)
                except Exception as err:  # noqa: BLE001
                    last_error = err
                    continue
            conn = None
            try:
                conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout, context=SSL_CONTEXT)
                conn.request("GET", target, headers=headers)
                resp = conn.getresponse()
                if resp.status == 404:
                    return ""
                if resp.status >= 400:
                    raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, None)
                chunks = []
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", "replace")
            except Exception as err:  # noqa: BLE001 — transient network failures
                last_error = err
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001
                        pass
    raise RuntimeError(f"GET {path} failed after {retries} attempts: {last_error}")


def _curl(url: str, timeout: float) -> str:
    """Fetch a page through curl, used when the Python stack truncates."""
    import subprocess

    result = subprocess.run(
        ["curl", "-sS", "--fail", "--max-time", str(int(timeout)),
         "--compressed", "-A", UA,
         "-H", "Accept-Language: en-US,en;q=0.9", "-H", f"Referer: {BASE}/", url],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl exited {result.returncode}: {result.stderr.decode()[:120]}")
    return result.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def text(fragment: str) -> str:
    """Plain text of an HTML fragment, with entities resolved."""
    value = TAG.sub(" ", fragment)
    value = html_module.unescape(value)
    value = value.replace("\xa0", " ")
    return WS.sub(" ", value).strip()


def tables(doc: str) -> list[str]:
    """Every top-level <table> in document order."""
    return re.findall(r"<table[^>]*>.*?</table>", doc, re.S)


def rows(table: str) -> list[str]:
    return re.findall(r"<tr[^>]*>.*?</tr>", table, re.S)


def cells(row: str) -> list[str]:
    return re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)


def find_table(doc: str, must_contain: str) -> str | None:
    for table in tables(doc):
        if must_contain in table:
            return table
    return None


def attr(fragment: str, name: str) -> str:
    match = re.search(rf'{name}="([^"]*)"', fragment)
    return html_module.unescape(match.group(1)) if match else ""


def player_id(slug: str) -> str:
    """
    The identity used for a player: the whole slug.

    Slugs mostly look like `sinner-8b8e8`, but not always — some are a bare name
    (`norrie`), some carry a multi-part surname (`reis-da-silva`), and some end in
    an empty segment (`lawrence-jr-`).  Taking the last dash segment as the id
    makes `reis-da-silva` and `dutra-da-silva` collide onto `da-silva`, so the
    full slug — which the source uses consistently in every link — is the id.
    """
    return slug


def player_link(fragment: str) -> tuple[str, str] | None:
    """`/player/sinner-8b8e8/` → (slug, id)."""
    match = re.search(r'href="/player/([^"/]+)/?"', fragment)
    if not match:
        return None
    slug = match.group(1)
    # (display slug, id): the display slug drops a trailing hash when there is one.
    if "-" in slug:
        base, _, tail = slug.rpartition("-")
        return base or slug, slug
    return slug, slug


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

RANK_BASE = "/ranking/atp-men/"


def parse_rankings(doc: str) -> list[dict]:
    """
    Parse one page of the ATP singles ranking.

    Row shape:
      <td class="rank first">1.</td>
      <td class="prevrank"><div class="oup">13</div></td>
      <td class="t-name"><a href="/player/sinner-8b8e8/">Sinner Jannik</a></td>
      <td class="tl"><a href="...">Italy</a></td>
      <td class="long-point">11500</td>
    """
    table = find_table(doc, "Player name")
    if not table:
        return []

    out: list[dict] = []
    for row in rows(table):
        if 'class="head"' in row:
            continue
        rank_cell = re.search(r'<td class="rank[^"]*">(.*?)</td>', row, re.S)
        name_cell = re.search(r'<td class="t-name">(.*?)</td>', row, re.S)
        if not rank_cell or not name_cell:
            continue

        rank = _int(text(rank_cell.group(1)).rstrip("."))
        link = player_link(name_cell.group(1))
        if rank is None or not link:
            continue
        slug, pid = link
        name = text(name_cell.group(1))

        move_cell = re.search(r'<td class="prevrank">(.*?)</td>', row, re.S)
        move, move_dir = _parse_move(move_cell.group(1) if move_cell else "")

        country = ""
        country_cell = re.search(r'<td class="tl">(.*?)</td>', row, re.S)
        if country_cell:
            code = re.search(r'class="fl fl-([a-z]{2})"', country_cell.group(1))
            country = text(country_cell.group(1))
            if code:
                country = country  # the flag ISO code is kept separately below
        flag = ""
        if country_cell:
            m = re.search(r'class="fl fl-([a-z]{2})"', country_cell.group(1))
            flag = m.group(1).upper() if m else ""

        point_cell = re.search(r'<td class="long-point">(.*?)</td>', row, re.S)
        points = _int(text(point_cell.group(1)).replace(",", "")) if point_cell else None

        out.append({
            "rank": rank,
            "id": pid,
            "slug": slug,
            "name": _order_name(name),
            "country": country,
            "flag": flag,
            "points": points,
            "move": move,
            "moveDir": move_dir,
        })
    return out


def _parse_move(fragment: str) -> tuple[int, str]:
    """`<div class="oup">13</div>` → (13, "up"); `<div>-</div>` → (0, "flat")."""
    body = re.search(r"<div[^>]*class=\"([^\"]*)\"[^>]*>(.*?)</div>", fragment, re.S)
    if not body:
        return 0, "flat"
    cls, value = body.group(1), text(body.group(2))
    if value in ("-", "", "\xa0"):
        return 0, "flat"
    number = _int(value)
    if number is None:
        return 0, "flat"
    # Tennis Explorer marks the direction with the class name.
    if "odown" in cls or "down" in cls:
        return -number, "down"
    return number, "up"


def _order_name(value: str) -> str:
    """
    Tennis Explorer prints "Sinner Jannik"; the dashboard shows "Jannik Sinner".
    Names with a particle or a single token are returned unchanged.
    """
    value = WS.sub(" ", value).strip()
    parts = value.split(" ")
    if len(parts) < 2:
        return value
    return " ".join(parts[1:] + parts[:1])


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Player detail
# ---------------------------------------------------------------------------

PLAYER_BASE = "/player/{slug}/"


def parse_player_detail(doc: str) -> dict:
    """
    The `plDetail` card:
      Sinner Jannik | Country: Italy | Height / Weight: 188 cm / 76 kg |
      Age: 25 (16. 8. 2001) | Current/Highest rank - singles: 1. / 1. |
      Current/Highest rank - doubles: - / 34. | Sex: man | Plays: right
    """
    table = find_table(doc, "Current/Highest rank")
    if not table:
        table = find_table(doc, "Country:")
    if not table:
        return {}
    blob = text(table)
    out: dict = {}

    country = re.search(r"Country:\s*([A-Za-z .'\-]+?)\s+(?:Height|Age|Current|Sex|Plays|$)", blob)
    if country:
        out["country"] = country.group(1).strip()

    hw = re.search(r"Height\s*/\s*Weight:\s*([\d.]+)?\s*cm\s*/\s*([\d.]+)?\s*kg", blob)
    height = re.search(r"Height\s*/\s*Weight:\s*([\d.]+)\s*cm", blob)
    weight = re.search(r"/\s*([\d.]+)\s*kg", blob)
    if height:
        out["height"] = int(float(height.group(1)))
    if weight:
        out["weight"] = int(float(weight.group(1)))

    age = re.search(r"Age:\s*(\d+)\s*\((\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\)", blob)
    if age:
        out["age"] = int(age.group(1))
        out["birth"] = f"{age.group(4)}-{int(age.group(3)):02d}-{int(age.group(2)):02d}"

    sgl = re.search(r"singles:\s*([\d-]+)\.\s*/\s*([\d-]+)\.", blob)
    if sgl:
        if sgl.group(1) != "-":
            out["rank"] = _int(sgl.group(1))
        if sgl.group(2) != "-":
            out["highRank"] = _int(sgl.group(2))

    dbl = re.search(r"doubles:\s*([\d-]+)\.\s*/\s*([\d-]+)\.", blob)
    if dbl and dbl.group(2) != "-":
        out["highRankDoubles"] = _int(dbl.group(2))

    plays = re.search(r"Plays:\s*(left|right)", blob, re.I)
    if plays:
        out["hand"] = plays.group(1).capitalize()

    # The card carries a portrait under /res/img/player/.
    photo = re.search(r'<img[^>]+src="(/res/img/player/[^"]+)"', table)
    if photo:
        out["photo"] = photo.group(1)
    return out


def parse_player_balance(doc: str) -> dict:
    """
    Year-by-year and surface W/L.

    Table header: Year | Summary | Clay | Hard | Indoors | Grass | Not set
    Summary row first ("Summary: 465/138 ..."), then one row per season.
    """
    table = find_table(doc, "Indoors")
    if not table:
        return {}
    header_row = None
    out_rows: list[list[str]] = []
    for row in rows(table):
        values = [text(c) for c in cells(row)]
        values = [v for v in values if v != ""]
        if not values:
            continue
        if values[0] == "Year":
            header_row = values
            continue
        if header_row:
            out_rows.append(values)
    if not header_row:
        return {}

    surfaces = header_row[2:]  # after Year, Summary
    seasons: dict = {}
    summary = None
    for values in out_rows:
        label = values[0]
        # values[1] is the overall record; the surface columns start at values[2].
        total = _record(values[1]) if len(values) > 1 else None
        record_cells = values[2:]
        parsed = {surfaces[i]: _record(v) for i, v in enumerate(record_cells) if i < len(surfaces)}
        parsed = {k: v for k, v in parsed.items() if v}
        if label.rstrip(":").lower() == "summary":
            summary = {"total": total, "bySurface": parsed}
            continue
        year = _int(label)
        if year is not None:
            seasons[year] = {"total": total, "bySurface": parsed}
    result: dict = {"seasons": seasons}
    if summary:
        result["career"] = summary
    return result


def _record(value: str) -> dict | None:
    """`"45/4"` → {"w": 45, "l": 4}; `"-"` → None."""
    match = re.match(r"(\d+)\s*/\s*(\d+)", str(value))
    if not match:
        return None
    return {"w": int(match.group(1)), "l": int(match.group(2))}


def parse_player_titles(doc: str) -> list[dict]:
    """
    The `titles` table lists, per season, the main-tour and lower-level titles.
    Tournament names appear on continuation rows with an empty year cell.
    """
    tables_found = [t for t in tables(doc) if 'class="result titles"' in t]
    if not tables_found:
        return []
    table = max(tables_found, key=len)

    out: list[dict] = []
    current: dict | None = None
    for row in rows(table):
        if 'class="head"' in row:
            continue
        values = [text(c) for c in cells(row)]
        values = [v for v in values if v != ""]
        if not values:
            continue
        year = _int(values[0])
        if year is not None:
            counts = values[1:]
            current = {
                "year": year,
                "main": _int(counts[0]) if counts and counts[0] != "-" else 0,
                "lower": _int(counts[1]) if len(counts) > 1 and counts[1] != "-" else 0,
                "events": [],
            }
            out.append(current)
        elif current is not None:
            # A continuation row carries the tournament name of a title won.
            current["events"].append(values[0])
    return out


# ---------------------------------------------------------------------------
# Match log
# ---------------------------------------------------------------------------

MONTHS = {
    "01": 1, "02": 2, "03": 3, "04": 4, "05": 5, "06": 6,
    "07": 7, "08": 8, "09": 9, "10": 10, "11": 11, "12": 12,
}

# Tennis Explorer labels early rounds relative to the draw ("1R" is the first
# round of that event), so the code is kept as printed and ordered instead.
ROUND_ORDER = {
    "Q1": 0, "Q2": 1, "Q3": 2,
    "1R": 3, "2R": 4, "3R": 5, "4R": 6, "R128": 3, "R64": 4, "R32": 5, "R16": 6,
    "RR": 4, "BR": 5,
    "QF": 7, "SF": 8, "F": 9, "W": 10,
}


def parse_match_log(doc: str, year: int, player_id: str) -> list[dict]:
    """
    A season's matches.

    The log is one table per tournament.  Inside it:
      <td class="first time">12.07.</td>            date (DD.MM.)
      <td class="s-color"><span title="grass">      surface
      <td class="t-name"><a><strong>Winner</strong></a> - <a>Loser</a></td>
      <td class="round" title="final">F</td>        round (title is the full name)
      <td class="tl"><a href="/match-detail/?id=">6-4, 6-4</a></td>   score
      <td class="course">1.21</td><td class="course">4.59</td>       odds
    The player marked with <strong> won.
    """
    table = find_table(doc, 'class="round"')
    if not table:
        return []

    out: list[dict] = []
    tournament = ""
    tournament_path = ""
    surface = ""
    for row in rows(table):
        cls = attr(row, "class")

        # Tournament heading row: carries the event name and its draw page.
        if 'class="head' in cls or '<th class="round"' in row:
            link = re.search(r'<td class="t-name"[^>]*>(.*?)</td>', row, re.S)
            if link:
                href = re.search(r'href="(/[^"]+)"', link.group(1))
                name = text(link.group(1))
                name = re.sub(r"^(Main tournaments|Lower level tournaments)\s*", "", name).strip()
                if name:
                    tournament = name
                    tournament_path = href.group(1) if href else ""
                    surface = _surface_from_row(row) or surface
            continue

        time_cell = re.search(r'<td class="first time">(.*?)</td>', row, re.S)
        name_cell = re.search(r'<td class="t-name">(.*?)</td>', row, re.S)
        if not time_cell or not name_cell:
            continue

        day_month = text(time_cell.group(1)).rstrip(".")
        date = _date(year, day_month)
        if not date:
            continue

        winner, loser, winner_is_me = _parse_pair(name_cell.group(1), player_id)
        if not winner:
            continue

        round_cell = re.search(r'<td class="round"([^>]*)>(.*?)</td>', row, re.S)
        round_code = ""
        round_name = ""
        if round_cell:
            round_code = text(round_cell.group(2))
            round_name = attr(round_cell.group(1), "title")

        score = ""
        match_id = ""
        score_cell = re.search(r'<td class="tl">(.*?)</td>', row, re.S)
        if score_cell:
            link = re.search(r'href="(/match-detail/\?id=\d+)"', score_cell.group(1))
            match_id = link.group(1).split("=")[-1] if link else ""
            score = text(score_cell.group(1))

        odds = [text(c) for c in re.findall(r'<td class="course">(.*?)</td>', row, re.S)]
        row_surface = _surface_from_row(row) or surface

        out.append({
            "date": date,
            "tournament": tournament,
            "tournamentPath": tournament_path,
            "surface": row_surface,
            "round": round_code.upper(),
            "roundOrder": ROUND_ORDER.get(round_code.upper(), 0),
            "roundName": round_name,
            "winner": winner,
            "loser": loser,
            "won": winner_is_me,
            "score": score,
            "matchId": match_id,
            "odds": odds,
        })
    return out


def _surface_from_row(row: str) -> str:
    match = re.search(r'<span title="([a-z ]+)"\s+style="background-color', row)
    return match.group(1).strip() if match else ""


def _date(year: int, day_month: str) -> str:
    match = re.match(r"(\d{1,2})\.\s*(\d{1,2})", day_month)
    if not match:
        return ""
    day, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _parse_pair(fragment: str, me: str) -> tuple[dict | None, dict | None, bool]:
    """
    Both players of a match, and whether `me` (the page's player) won.

    The FIRST player listed is always the winner, whatever the score; `<strong>`
    marks the page's own player instead, so it cannot be used to decide the
    result.  (This is verified against the season W/L table in verify.py, which
    independently reports the same totals.)
    """
    # Split on the " - " separator that sits between the two player links.
    parts = re.split(r"\s+-\s+(?=<a\s)", fragment, maxsplit=1)
    if len(parts) != 2:
        parts = re.split(r"\s+-\s+", fragment, maxsplit=1)
    if len(parts) != 2:
        return None, None, False

    def side(chunk: str) -> tuple[dict | None, bool]:
        link = re.search(r'href="/player/([^"/]+)/?"[^>]*>(.*?)</a>', chunk, re.S)
        if not link:
            return None, False
        slug = link.group(1)
        pid = player_id(slug)
        strong = "<strong>" in chunk
        return {"id": pid, "slug": slug, "name": _order_name(text(link.group(2)))}, strong

    left, left_strong = side(parts[0])
    right, right_strong = side(parts[1])
    if not left or not right:
        return None, None, False

    return left, right, left["id"] == me


# ---------------------------------------------------------------------------
# Daily results
# ---------------------------------------------------------------------------

RESULTS_BASE = "/results/"


def parse_results_day(doc: str) -> dict:
    """
    One day of results across every tournament in play.

    Per tournament there is a heading row carrying the name and draw-page link,
    then one PAIR of rows per match sharing an id stem: the winner's row is
    `s10` and the loser's is `s10b`.  The winner is therefore the row whose id
    does not end in "b" — the `fRow` class only appears on some of them, and the
    `result` cell (sets won) confirms the order.

    Returns {"tournaments": {path: {...}}, "matches": [...]}.
    """
    candidates = [t for t in tables(doc) if 'class="head flags"' in t]
    if not candidates:
        return {"tournaments": {}, "matches": []}
    table = max(candidates, key=len)

    tournaments: dict[str, dict] = {}
    matches: list[dict] = []
    current: dict | None = None
    pending: dict | None = None

    for row in rows(table):
        cls = attr(row, "class")

        # ---------------------------------------------------------- heading
        if "head" in cls and "<th" not in row:
            link = re.search(r'<td class="t-name"[^>]*>(.*?)</td>', row, re.S)
            if link:
                href = re.search(r'href="([^"]+)"', link.group(1))
                path = href.group(1) if href else ""
                name = text(link.group(1))
                flag = re.search(r'class="fl fl-([a-z]{2})"', link.group(1))
                if path:
                    current = tournaments.setdefault(path, {
                        "path": path,
                        "name": name,
                        "flag": flag.group(1).upper() if flag else "",
                        "surface": _surface_from_row(row),
                        "matches": 0,
                    })
            continue

        if current is None:
            continue

        row_id = attr(row, "id")
        if not row_id:
            continue

        parsed = _parse_result_row(row, row_id)

        if row_id.endswith("b"):
            # Loser row: close the match opened by the winner row above it.
            # A match with no set scores has not been completed (or is a
            # walkover), and one whose two sides resolve to the same id is a
            # source artefact — neither is a result.
            if (pending is not None and parsed["player"]["name"] and pending["player"]["name"]
                    and parsed["player"]["id"] != pending["player"]["id"]
                    and any(v.strip() for v in (pending["score"] or []))):
                matches.append({
                    "winner": pending["player"],
                    "loser": parsed["player"],
                    "sets": pending["sets"],
                    "score": pending["score"],
                    "tournament": current["name"],
                    "tournamentPath": current["path"],
                    "time": pending["time"],
                })
                current["matches"] += 1
            pending = None
            continue

        # Winner row: hold it until its partner row arrives.
        pending = parsed

    return {"tournaments": tournaments, "matches": matches}


def _parse_result_row(row: str, row_id: str) -> dict:
    """One side of a result pair."""
    time_cell = re.search(r'<td class="first time"[^>]*>(.*?)</td>', row, re.S)
    name_cell = re.search(r'<td class="t-name">(.*?)</td>', row, re.S)
    link = re.search(r'href="/player/([^"/]+)/?"[^>]*>(.*?)</a>', name_cell.group(1), re.S) if name_cell else None
    slug = link.group(1) if link else ""
    pid = player_id(slug)

    seed = ""
    if name_cell:
        seed_match = re.search(r"\((\d+)\)", text(name_cell.group(1)))
        seed = seed_match.group(1) if seed_match else ""

    result_cell = re.search(r'<td class="result">(.*?)</td>', row, re.S)
    set_cells = re.findall(r'<td class="score">(.*?)</td>', row, re.S)
    # The last two score columns are the H and A odds; the rest are set scores.
    scores = [text(c) for c in set_cells]
    odds = scores[-2:] if len(scores) >= 2 and all(_is_odds(v) for v in scores[-2:]) else []
    if odds:
        scores = scores[:-2]

    return {
        "rowId": row_id,
        "time": text(time_cell.group(1)) if time_cell else "",
        "player": {
            "id": pid,
            "slug": slug,
            "name": _order_name(text(link.group(2))) if link else "",
            "seed": seed,
        },
        "sets": _int(text(result_cell.group(1))) if result_cell else None,
        "score": [v for v in scores if v not in ("", "\xa0")],
        "odds": odds,
        "pending": None,
    }


def _is_odds(value: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}\.\d{2}", value.strip()))


# ---------------------------------------------------------------------------
# Tournament draw
# ---------------------------------------------------------------------------

def parse_event_draw(doc: str, year: int) -> dict:
    """
    A tournament's complete singles draw.

    Same row pairing as the daily results (id `r0` is the winner, `r0b` the
    loser), with an extra round cell:
      <td title="final" rowspan="2" style="0:round">F</td>
    so the `title` gives the round's full name and the text gives its code.

    Returns {"rounds": {code: {"label", "order", "matches"}}, "players": {...}}.
    """
    candidates = [t for t in tables(doc) if 'class="result"' in t and 'class="round"' in t]
    if not candidates:
        return {"rounds": {}, "players": {}}
    table = max(candidates, key=len)

    rounds: dict[str, dict] = {}
    players: dict[str, dict] = {}
    pending: dict | None = None

    for row in rows(table):
        row_id = attr(row, "id")
        if not row_id:
            continue

        parsed = _parse_draw_row(row, year)
        if not parsed:
            continue

        pid = parsed["player"]["id"]
        if pid and pid not in players:
            players[pid] = parsed["player"]

        if row_id.endswith("b"):
            if pending is not None and parsed["player"]["name"] and pending["player"]["name"]:
                code = pending["round"] or ""
                entry = rounds.setdefault(code, {
                    "label": code,
                    "order": ROUND_ORDER.get(code.upper(), 0),
                    "title": pending["roundTitle"],
                    "matches": [],
                })
                entry["matches"].append({
                    "date": pending["date"],
                    "time": pending["time"],
                    "winner": pending["player"],
                    "loser": parsed["player"],
                    "sets": pending["sets"],
                    "score": pending["score"],
                })
            pending = None
            continue

        pending = parsed

    # Newest round first, and inside a round the latest match first.
    for entry in rounds.values():
        entry["matches"].sort(key=lambda m: m["date"], reverse=True)
    ordered = {k: rounds[k] for k in sorted(rounds, key=lambda k: -rounds[k]["order"])}
    return {"rounds": ordered, "players": players}


def _parse_draw_row(row: str, year: int) -> dict | None:
    name_cell = re.search(r'<td class="t-name">(.*?)</td>', row, re.S)
    if not name_cell:
        return None
    link = re.search(r'href="/player/([^"/]+)/?"[^>]*>(.*?)</a>', name_cell.group(1), re.S)
    if not link:
        return None
    slug = link.group(1)
    pid = player_id(slug)
    seed = re.search(r"\((\d+)\)", text(name_cell.group(1)))

    time_cell = re.search(r'<td class="first time"[^>]*>(.*?)</td>', row, re.S)
    stamp = text(time_cell.group(1)) if time_cell else ""
    dates = re.findall(r"(\d{1,2})\.(\d{1,2})\.", stamp)
    date = f"{year:04d}-{int(dates[0][1]):02d}-{int(dates[0][0]):02d}" if dates else ""
    times = re.findall(r"(\d{1,2}:\d{2})", stamp)

    round_cell = re.search(r'<td title="([^"]*)"[^>]*class="[^"]*round[^"]*"[^>]*>(.*?)</td>', row, re.S)
    if not round_cell:
        round_cell = re.search(r'<td title="([^"]*)"[^>]*>(.*?)</td>', row, re.S)
    round_title = round_cell.group(1) if round_cell else ""
    round_code = text(round_cell.group(2)) if round_cell else ""

    result_cell = re.search(r'<td class="result">(.*?)</td>', row, re.S)
    scores = [text(c) for c in re.findall(r'<td class="score">(.*?)</td>', row, re.S)]

    return {
        "date": date,
        "time": times[0] if times else "",
        "round": round_code,
        "roundTitle": round_title,
        "player": {
            "id": pid,
            "slug": slug,
            "name": _order_name(text(link.group(2))),
            "seed": seed.group(1) if seed else "",
        },
        "sets": _int(text(result_cell.group(1))) if result_cell else None,
        "score": [v for v in scores if v not in ("", "\xa0")],
    }


# ---------------------------------------------------------------------------
# Event header
# ---------------------------------------------------------------------------

# Prize money contains thousands separators, so the amount may not exclude commas.
EVENT_HEAD = re.compile(
    r"\((?P<country>[^()]*)\)\s*\((?P<prize>[^()]*?)\s*,\s*(?P<surface>[a-z ]+?)\s*,\s*(?P<gender>men|women)\b",
    re.I,
)


def parse_event_meta(doc: str) -> dict:
    """
    Country, prize money and surface from an event page's heading line.

    The line reads e.g. ``Wimbledon 2026 (Great Britain) (74,292,561 €, grass, men)``,
    which is the only place the event page states its surface — the draw rows
    themselves carry no surface cell.
    """
    # The heading sits after the navigation tables, so the whole document is
    # searched; the pattern is specific enough not to match anything else.
    blob = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", doc))
    match = EVENT_HEAD.search(blob)
    if not match:
        return {}
    prize_raw = match.group("prize").strip()
    prize = None
    digits = re.sub(r"[^\d]", "", prize_raw)
    if digits:
        prize = int(digits)
    currency = "EUR" if "€" in prize_raw else "USD" if "$" in prize_raw else ""
    return {
        "country": match.group("country").strip(),
        "surface": match.group("surface").strip().capitalize(),
        "prize": prize,
        "currency": currency,
    }


# ---------------------------------------------------------------------------
# Tour calendar
# ---------------------------------------------------------------------------

CALENDAR_BASE = "/calendar/atp-men/"


def parse_calendar(doc: str) -> list[dict]:
    """
    The season calendar: every tournament, played or scheduled.

    One row per tournament, with a second row per tournament for the doubles
    draw (which is skipped):
      <tr class="one actual" data-type="main">
        <td class="first shortdate" rowspan="2">30.08.<br>2026</td>
        <th class="t-name" rowspan="2"><a href="/us-open/2026/atp-men/"><strong>US Open</strong></a></th>
        <td class="s-color" rowspan="2"><span title="Hard" …></td>
        <td class="tr" rowspan="2">37,840,000 $</td>
        <td class="draw" title="number of players in singles">128</td>
        <td class="t-name"><a href="/player/…">Zverev A.</a></td>
      </tr>

    `data-type` gives the tour tier, and the `actual` class marks a tournament
    that has been played — which is how upcoming events are distinguished without
    guessing from dates.
    """
    tables_found = [t for t in tables(doc) if 'class="shortdate"' in t]
    if not tables_found:
        return []
    table = max(tables_found, key=len)

    out: list[dict] = []
    month = ""
    for row in rows(table):
        classes = attr(row, "class")

        # Month separator row.
        month_cell = re.search(r'<td class="tl"[^>]*>(.*?)</td>', row, re.S)
        if month_cell:
            month = text(month_cell.group(1))
            continue

        # The doubles companion row has no date cell at all.
        date_cell = re.search(r'<td class="first shortdate[^"]*"[^>]*>(.*?)</td>', row, re.S)
        if not date_cell:
            continue

        link = re.search(r'<th class="t-name"[^>]*>.*?<a href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        if not link:
            continue
        path = link.group(1)
        name = text(link.group(2))

        stamp = text(date_cell.group(1))
        date_match = re.search(r"(\d{1,2})\.(\d{1,2})\.\s*(\d{4})", stamp)
        if not date_match:
            continue
        date = f"{date_match.group(3)}-{int(date_match.group(2)):02d}-{int(date_match.group(1)):02d}"

        surface_cell = re.search(r'<td class="s-color"[^>]*>(.*?)</td>', row, re.S)
        surface = ""
        if surface_cell:
            title = re.search(r'title="([^"]+)"', surface_cell.group(1))
            surface = title.group(1).strip().capitalize() if title else ""

        prize_cell = re.search(r'<td class="tr"[^>]*>(.*?)</td>', row, re.S)
        prize_raw = text(prize_cell.group(1)) if prize_cell else ""
        prize_number = re.sub(r"[^\d]", "", prize_raw)

        draw_cell = re.search(r'<td class="draw"[^>]*title="number of players in singles"[^>]*>(.*?)</td>', row, re.S)
        if not draw_cell:
            draw_cell = re.search(r'<td class="draw"[^>]*>(.*?)</td>', row, re.S)

        winner_cell = re.search(r'<td class="t-name">(.*?)</td>', row, re.S)
        winner = None
        if winner_cell:
            wlink = re.search(r'href="/player/([^"/]+)/?"[^>]*>(.*?)</a>', winner_cell.group(1), re.S)
            if wlink:
                winner = {"id": wlink.group(1), "name": _order_name(text(wlink.group(2)))}
            elif text(winner_cell.group(1)) not in ("-", ""):
                winner = {"id": "", "name": text(winner_cell.group(1))}

        out.append({
            "path": path,
            "name": name,
            "date": date,
            "month": month,
            "year": int(date_match.group(3)),
            "surface": surface,
            "prize": int(prize_number) if prize_number else None,
            "currency": "EUR" if "€" in prize_raw else "USD" if "$" in prize_raw else "",
            "draw": _int(text(draw_cell.group(1))) if draw_cell else None,
            "winner": winner,
            "type": attr(row, "data-type") or "",
            # The `actual` class only marks the tournaments of the current week, so
            # a published singles champion is the reliable sign that an event has
            # been played.
            "played": bool(winner),
        })
    return out
