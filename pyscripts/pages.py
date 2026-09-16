"""
Panel renderers for the ATP dashboard.

Seven panels plus player profiles and event draws.  Everything is written as
complete HTML; the interactive parts use CSS `:target`, so a link such as
``#sort-pct`` reveals a pre-rendered section and the language anchors swap the
bilingual text — no script runs on the page.

The ATP source reports results and win/loss records rather than the WTA feed's
aggregated serve splits, so the statistics panel is built from what the tour
actually publishes: season wins, win rate, titles, per-surface win rates and
weekly ranking movement.
"""

from __future__ import annotations

from render import (
    Context,
    bi,
    esc,
    iso_date,
    num,
    pct,
    short_date,
    timestamp,
)
from templates import page_head, player_cell, shell

SURFACES = [("Hard", "硬地"), ("Clay", "红土"), ("Grass", "草地"), ("Indoors", "室内")]


def _record(w, l) -> str:
    if w is None or l is None:
        return "—"
    return f"{w}–{l}"


def _win_pct(w, l):
    total = (w or 0) + (l or 0)
    return (w or 0) / total * 100 if total else None


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def overview(ctx: Context) -> str:
    counts = ctx.counts
    no1 = ctx.players[0] if ctx.players else None
    season = ctx.season

    kpis = [
        ("排名球员", "Ranked players", num(counts.get("rankedPlayers")),
         bi("单打世界排名收录", "singles ranking depth"), "var(--gold-500)"),
        ("赛季赛事", "Season events", num(counts.get("events")),
         bi(f"{counts.get('champions', 0)} 站已产生冠军", f"{counts.get('champions', 0)} with a champion"),
         "var(--grass-400)"),
        ("赛季比赛", "Season matches", num(counts.get("seasonMatches")),
         bi("已收录完整赛果", "complete results captured"), "var(--line-white)"),
        ("收录签表", "Draws", num(counts.get("eventDraws")),
         bi("逐轮完整签表", "round-by-round draws"), "var(--grass-500)"),
        ("世界第一", "World No.1",
         (no1.get("zh") or no1.get("name")) if no1 else "—",
         bi(f"{num(no1.get('points'))} 积分", f"{num(no1.get('points'))} pts") if no1 else "",
         "var(--gold-400)"),
        ("交手配对", "H2H pairings", num(counts.get("h2hPairings")),
         bi(f"{num(counts.get('namedPlayers'))} 名球员", f"{num(counts.get('namedPlayers'))} players"),
         "var(--gold-500)"),
    ]
        # 数值型用大号英文数字字体；文本型（如世界第一的球员名）用缩小的中文版式。
    def _value_class(value: str) -> str:
        return '' if str(value).lstrip().startswith(('#', '0', '1', '2', '3', '4', '5',
                                                     '6', '7', '8', '9', '$')) or value in ('—',) else ' text'

    kpi_html = "".join(
        f'<div class="kpi" style="--kpi-accent:{accent}">'
        f'<div class="kpi-label">{bi(zh, en)}</div>'
        f'<div class="kpi-value' + _value_class(value) + '">' + esc(value) + '</div>'
        f'<div class="kpi-sub">{sub}</div></div>'
        for zh, en, value, sub, accent in kpis
    )

    champions = [c for c in ctx.champions if c["year"] == season][:40]
    champ_html = "".join(
        f'<div class="champ-card">'
        f'<div class="champ-top">{ctx.avatar(c["player"], 34, "champ-avatar")}'
        f'<div class="champ-name"><span class="cup" aria-hidden="true">🏆</span>'
        f'{ctx.name(c["player"])}</div></div>'
        f'<div class="champ-ev">{ctx.tournament(c["event"])}</div>'
        f'<div class="champ-ev">{esc(short_date(c["date"]))} · {ctx.level_tag(c["level"])}</div>'
        f"</div>"
        for c in champions
    ) or '<div class="empty-state">' + bi("暂无冠军数据", "No champions yet") + "</div>"

    recent = ctx.results[:12]
    recent_html = "".join(_result_row(ctx, r) for r in recent) or (
        '<div class="empty-state">' + bi("暂无赛果", "No results yet") + "</div>")

    top10 = "".join(
        f'<div class="mini-row" style="padding:7px 18px">'
        f'<span class="n"><span class="i" style="font-family:var(--font-en);'
        f'color:var(--ivory-mute);width:20px;display:inline-block">{i + 1}</span>'
        f'<a href="player-{p["id"]}.html" style="margin-left:8px">{ctx.name(p)}</a></span>'
        f'<span class="v">{num(p["points"])}</span></div>'
        for i, p in enumerate(ctx.players[:10])
    )

    boards_html = "".join(_board_mini(ctx, b) for b in ctx.boards[:4])
    career_html = "".join(
        _career_col(ctx, zh, en, ctx.career.get(key, [])[:8], fmt)
        for zh, en, key, fmt in [
            ("生涯单打冠军", "Career singles titles", "titles", lambda p: num(p.get("value") or p.get("titles"))),
            ("生涯胜场", "Career match wins", "careerWins", lambda p: num(p.get("value") or p.get("won"))),
            ("生涯胜率", "Career win rate", "careerPct", lambda p: pct(p.get("value"))),
        ]
    )

    body = f'''
<section class="hero">
  <div class="hero-court" aria-hidden="true"></div>
  <div class="hero-content">
    <div class="hero-eyebrow"><span class="dot-live"></span>
      <span class="cn">男子职业网球巡回赛</span><span class="en">ATP TOUR</span></div>
    <h1 class="hero-title">
      <span class="cn">{esc(season)} 赛季</span>
      <span class="en">{esc(season)} SEASON</span>
    </h1>
    <p class="hero-sub">{bi(
        "数据来源：ATP 官方单打世界排名与逐站完整赛果 · 涵盖排名变动、赛季战绩、场地胜率、冠军榜与生涯交手记录",
        "Built from the official ATP singles ranking and complete tour results — ranking movement, season records, surface win rates, titles and career head-to-heads",
    )}</p>
    <div class="hero-meta">
      <span><i class="cn">更新日期</i><i class="en">Updated</i><b>{esc(timestamp(ctx.meta.get("generatedAt")))}</b></span>
      <span><i class="cn">排名周</i><i class="en">Rankings week</i><b>{esc(timestamp(ctx.meta.get("rankingsAsOf")))}</b></span>
      <span><i class="cn">收录球员</i><i class="en">Players</i><b>{num(counts.get("namedPlayers"))}</b></span>
    </div>
  </div>
</section>

<div class="wrap">
  <h2 class="sec-title"><span class="cn">赛季概览</span><span class="en">Season At A Glance</span></h2>
  <div class="kpi-grid">{kpi_html}</div>

  <div class="two-col">
    <div class="panel">
      <div class="panel-head"><h3>{bi("冠军墙", "Champions")}</h3>
        <span class="panel-note">{bi(f"{len(champions)} 站赛事", f"{len(champions)} events")}</span></div>
      <div class="champion-wall">{champ_html}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>{bi("最新赛果", "Latest Results")}</h3>
        <a class="panel-more" href="results.html">{bi("全部赛果", "All results")} →</a></div>
      <div class="recent-list">{recent_html}</div>
    </div>
  </div>

  <div class="two-col">
    <div class="panel">
      <div class="panel-head"><h3>{bi("世界排名前十", "Top 10")}</h3>
        <a class="panel-more" href="rankings.html">{bi("完整排名", "Full ranking")} →</a></div>
      <div class="mini-boards">{top10}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>{bi("本赛季领跑", "Season Leaders")}</h3>
        <a class="panel-more" href="stats.html">{bi("全部榜单", "All boards")} →</a></div>
      <div class="mini-boards">{boards_html}</div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-head"><h3>{bi("生涯领跑", "Career Leaders")}</h3>
      <span class="panel-note">{bi("现役排名球员中的历史累计", "All-time among currently ranked players")}</span></div>
    <div class="career-grid">{career_html}</div>
  </div>
</div>
'''
    return shell(ctx, title=f"{season} 赛季总览",
                 active="index.html", body=body,
                 jsonld={
                     "@context": "https://schema.org",
                     "@type": "WebSite",
                     "name": "ATP Tour Data Dashboard",
                     "inLanguage": "zh-CN",
                     "url": "https://moonquake2004.github.io/atp-tour-dashboard/",
                 })


BOARD_ZH = {
    "seasonWins": "赛季胜场", "seasonWinPct": "赛季胜率", "careerTitles": "生涯冠军",
    "seasonTitles": "赛季冠军", "surfaceHard": "硬地胜率", "surfaceClay": "红土胜率",
    "surfaceGrass": "草地胜率", "surfaceIndoors": "室内胜率", "climbers": "排名上升",
}


def _board_mini(ctx: Context, board: dict) -> str:
    top = board["rows"][0]["value"] if board["rows"] else 1
    return (
        f'<div class="mini-board"><div class="mini-head">'
        f'{bi(BOARD_ZH.get(board["key"], ""), board["label"])}'
        f'<span>{esc("胜率" if board["unit"] == "%" else "总数")}</span></div>'
        + "".join(
            f'<div class="mini-row"><span class="n"><a href="player-{r["id"]}.html">'
            f'{esc(r.get("zh") or r["name"])}</a></span>'
            f'<span class="v">{pct(r["value"]) if board["unit"] == "%" else num(r["value"])}</span>'
            f'<span class="mini-bar" style="grid-column:1/-1"><i style="width:'
            f'{max(2, (r["value"] / top * 100) if top else 2):.1f}%"></i></span></div>'
            for r in board["rows"][:5]
        )
        + "</div>"
    )


def _career_col(ctx: Context, zh, en, rows, fmt) -> str:
    inner = "".join(
        f'<div class="career-row"><span class="i">{i + 1}</span>'
        f'<span class="n"><a href="player-{p["id"]}.html">{esc(p.get("zh") or p["name"])}</a></span>'
        f'<span class="v">{fmt(p)}</span></div>'
        for i, p in enumerate(rows)
    )
    return f'<div class="career-col"><h4>{bi(zh, en)}</h4>{inner}</div>'


def _result_row(ctx: Context, row: dict) -> str:
    winner, loser = row["winner"], row["loser"]
    seed_w = f'<span class="rank">[{row["seedW"]}]</span>' if row.get("seedW") else ""
    seed_l = f'<span class="rank">[{row["seedL"]}]</span>' if row.get("seedL") else ""
    event = ctx.tournament(row["event"])
    return (
        '<div class="result-row">'
        f'<div class="result-date">{esc(iso_date(row["date"]))}</div>'
        '<div class="result-main"><div class="result-players">'
        f'{ctx.avatar(winner, 26)}'
        f'<a class="w" href="player-{winner["id"]}.html">{ctx.name(winner)}</a>{seed_w}'
        f'<span class="d">d.</span>{ctx.avatar(loser, 26)}'
        f'<a class="l" href="player-{loser["id"]}.html">{ctx.name(loser)}</a>{seed_l}'
        "</div>"
        f'<div class="result-ev">{event}{ctx.surface_chip(row["surface"])}'
        f'{ctx.level_tag(row["level"])}</div></div>'
        f'<div class="result-score">{esc(row["score"])}</div></div>'
    )


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

RANK_SORTS = [("points", "积分", "Points"), ("name", "姓名", "Name"),
              ("age", "年龄", "Age"), ("move", "变动", "Move")]


def rankings(ctx: Context) -> str:
    top3 = ctx.players[:3]
    podium = "".join(
        f'<a class="podium-card g{i + 1}" href="player-{p["id"]}.html">'
        f'<span class="podium-n">No.{p["rank"]}</span>'
        f'{ctx.avatar(p, 76)}'
        f'<div class="podium-name">{ctx.name(p)}</div>'
        f'<div class="podium-pts">{num(p["points"])}</div>'
        f'<div class="podium-country">{esc(ctx.zh.get("countries", {}).get(p["country"], p["country"]))}</div></a>'
        for i, p in enumerate(top3)
    )

    def table(rows: list[dict], sort_key: str) -> str:
        def row(p: dict) -> str:
            age = p.get("age") if p.get("age") is not None else "—"
            high = f'#{p["highRank"]}' if p.get("highRank") else "—"
            return (
                f'<tr><td>{p["rank"]}</td>'
                f'<td class="l">{player_cell(ctx, p, avatar_on=(sort_key == "points"))}</td>'
                f'<td class="c"><span class="tb-flag">{ctx.country(p["country"])}</span></td>'
                f'<td>{ctx.move(p["move"])}</td>'
                f'<td class="tb-num">{age}</td>'
                f'<td class="tb-num">{high}</td>'
                f'<td class="tb-num">{num(p["points"])}</td></tr>'
            )

        body = "".join(row(p) for p in rows)
        return (
            '<table class="rank-table"><thead><tr>'
            f'<th class="c-pos">{bi("名次", "#")}</th><th class="c-player">{bi("球员", "Player")}</th>'
            f'<th class="c-country">{bi("国家/地区", "Country")}</th><th class="c-move">{bi("变动", "Move")}</th>'
            f'<th class="c-age">{bi("年龄", "Age")}</th><th class="c-ev">{bi("最高", "High")}</th>'
            f'<th class="c-pts">{bi("积分", "Points")}</th></tr></thead>'
            f"<tbody>{body}</tbody></table>"
        )

    # The default view is emitted LAST: the other views hide it with the sibling
    # combinator, which only reaches elements that come after them.
    ordered = [k for k, _, _ in RANK_SORTS if k != "points"] + ["points"]
    tables = "".join(
        f'<div class="rank-body" id="sort-{key}"><div class="table-scroll">'
        f'{table(sorted(ctx.players, key=lambda p: _rank_key(p, key)), key)}</div></div>'
        for key in ordered
    )

    body = f'''
<div class="wrap">
  {page_head("ATP Rankings · 官方单打排名", "", "官方单打排名", "Official singles ranking",
             f'共 {num(len(ctx.players))} 位球员，名次变动与官方公布的上周排名对比。',
             f'{num(len(ctx.players))} ranked players, with movement against the previous published week.')}
  <div class="rank-podium">{podium}</div>
  <div class="sort-bar">
    <span class="sort-label">{bi("排序", "Sort")}</span>
    <div class="seg-group sm">
      <a class="seg" href="#sort-points">{bi("积分", "Points")}</a>
      <a class="seg" href="#sort-name">{bi("姓名", "Name")}</a>
      <a class="seg" href="#sort-age">{bi("年龄", "Age")}</a>
      <a class="seg" href="#sort-move">{bi("变动", "Move")}</a>
    </div>
    <span class="dim" style="font-size:11.5px">{bi("默认按排名先后", "Default order is by ranking")}</span>
  </div>
  <div class="panel">
    <div class="rank-head"><div>
      <h3>{bi("单打世界排名", "Singles World Ranking")}</h3>
      <p class="rank-desc">{bi("排名积分与名次变动取自 ATP 官方榜单。",
                               "Points and movement are as published on the ATP ranking.")}</p>
    </div><div class="rank-updated">{esc(timestamp(ctx.meta.get("rankingsAsOf")))}</div></div>
    {tables}
  </div>
</div>
'''
    return shell(ctx, title="排名 · World Rankings", active="rankings.html", body=body)


def _rank_key(player: dict, key: str):
    if key == "name":
        return player["name"]
    if key == "age":
        return player.get("age") if player.get("age") is not None else 999
    if key == "move":
        return -(player.get("move") or 0)
    return -player["points"]


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


def players_page(ctx: Context) -> str:
    counts: dict[str, int] = {}
    for p in ctx.players:
        counts[p["country"]] = counts.get(p["country"], 0) + 1
    top_countries = sorted(counts.items(), key=lambda kv: -kv[1])[:14]

    chips = f'<a class="chip" href="#all">{bi("全部球员", "All players")}</a>' + "".join(
        f'<a class="chip" href="#c-{esc(_anchor(code))}">'
        f'{esc(ctx.zh.get("countries", {}).get(code, code))} {count}</a>'
        for code, count in top_countries
    )

    sections = ['<div class="player-grid" id="all">'
                + "".join(_player_card(ctx, p) for p in ctx.players) + "</div>"]
    for code, _ in top_countries:
        subset = [p for p in ctx.players if p["country"] == code]
        sections.append(f'<div class="player-grid" id="c-{esc(_anchor(code))}">'
                        + "".join(_player_card(ctx, p) for p in subset) + "</div>")

    body = f'''
<div class="wrap">
  {page_head("Player directory · 球员名录", "", "所有排名球员，一处查全", "Every ranked player, in one place",
             f'共 {num(len(ctx.players))} 位球员的生涯战绩、最高排名与赛季场地胜率。',
             f'Career records, high rankings and season surface win rates for all {num(len(ctx.players))} ranked players.')}
  <div class="filter-bar"><div class="chips">{chips}</div></div>
  {"".join(sections)}
</div>
'''
    return shell(ctx, title="球员 · Players", active="players.html", body=body)


def _anchor(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(value).lower())


def _player_card(ctx: Context, player: dict) -> str:
    season = player.get("season") or {}
    wins, losses = season.get("w"), season.get("l")
    win_pct = _win_pct(wins, losses)
    accent = "var(--gold-500)" if (wins or 0) > (losses or 0) and wins else "var(--hard-600)"
    age = player.get("age")
    age_text = f" · {age} 岁" if age is not None else ""
    career = player.get("career") or {}
    titles = (player.get("titles") or {}).get("main")
    country = esc(ctx.zh.get("countries", {}).get(player["country"], player["country"]))
    hand = player.get("hand") or ""
    high = f'#{player["highRank"]}' if player.get("highRank") else "—"
    return (
        f'<a class="player-card" href="player-{player["id"]}.html" style="--pc-accent:{accent}">'
        f'<div class="pc-top">{ctx.avatar(player, 54)}'
        f'<div class="pc-id"><span class="pc-rank">No.{player["rank"]} · {num(player["points"])} pts</span>'
        f'<span class="pc-name">{bi(player.get("zh") or player["name"], player["name"])}</span>'
        f'<span class="pc-country">{country}{age_text}</span></div></div>'
        f'<div class="pc-stats">'
        f'<div class="pc-stat"><b>{_record(wins, losses)}</b><span>{ctx.season} W–L</span></div>'
        f'<div class="pc-stat"><b>{titles if titles is not None else "—"}</b><span>冠军 Titles</span></div>'
        f'<div class="pc-stat"><b>{f"{win_pct:.0f}%" if win_pct else "—"}</b><span>胜率 Win %</span></div></div>'
        f'<div class="pc-serve">'
        f'<span>生涯 <b>{_record(career.get("w"), career.get("l"))}</b></span>'
        f'<span>最高 <b>{high}</b></span>'
        f'{f"<span>持拍 <b>{esc(hand)}</b></span>" if hand else ""}'
        f'</div></a>'
    )


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

# The source's calendar only lists tournaments up to the current week, so there
# is no "upcoming" view to offer — a filter that is always empty would mislead.
CAL_FILTERS = [("all", "全部", "All", lambda e, today: True),
               ("current", "进行中", "Ongoing", lambda e, today: e["start"] <= today <= e["end"]),
               ("past", "已完成", "Completed", lambda e, today: e["end"] < today)]

MONTH_ZH = {"01": "1 月", "02": "2 月", "03": "3 月", "04": "4 月", "05": "5 月", "06": "6 月",
            "07": "7 月", "08": "8 月", "09": "9 月", "10": "10 月", "11": "11 月", "12": "12 月"}
MONTH_EN = {"01": "January", "02": "February", "03": "March", "04": "April", "05": "May", "06": "June",
            "07": "July", "08": "August", "09": "September", "10": "October", "11": "November", "12": "December"}


def calendar(ctx: Context) -> str:
    """
    The tour calendar with status filters.

    Each filter is a complete pre-built list grouped by month, revealed by
    `:target` on the filter anchors, so the filter works with no script.  The
    anchors sit inside `.cal-scope` as siblings of the filter bar, which also lets
    the active chip be highlighted.
    """
    today = (ctx.meta.get("generatedAt") or "")[:10]
    counts = {key: sum(1 for e in ctx.calendar if match(e, today)) for key, _, _, match in CAL_FILTERS}

    chips = "".join(
        f'<a class="chip" href="#cal-anchor-{key}">{bi(zh, en)}'
        f'<span class="chip-n">{counts[key]}</span></a>'
        for key, zh, en, _ in CAL_FILTERS
    )

    views = []
    for key, _, _, match in CAL_FILTERS:
        rows = [e for e in ctx.calendar if match(e, today)]
        rows.sort(key=lambda e: (e["year"], e["start"]), reverse=True)
        groups: dict[str, list[dict]] = {}
        for event in rows:
            groups.setdefault(event["start"][:7], []).append(event)
        sections = "".join(
            f'<div class="cal-month"><div class="cal-month-head">'
            f'<span class="cn">{esc(_month(month))}</span>'
            f'<span class="en">{esc(_month(month, True))}</span>'
            f'<span class="cal-month-n">{bi(f"{len(items)} 站", f"{len(items)} events")}</span></div>'
            + "".join(_calendar_row(ctx, e, today) for e in items)
            + "</div>"
            for month, items in groups.items()
        )
        views.append(f'<div class="cal-view" id="cal-{key}">{sections}'
                     + ("" if rows else '<div class="empty-state">' + bi("暂无赛事", "No events") + "</div>")
                     + "</div>")

    anchors = "".join(f'<div id="cal-anchor-{key}" class="cal-anchor"></div>'
                      for key, _, _, _ in CAL_FILTERS)

    body = f'''
<div class="wrap">
  {page_head("Tour calendar · 巡回赛赛程", "", "ATP 赛季，逐站呈现", "The ATP season, event by event",
             "可按状态筛选：全部 / 进行中 / 已完成。每站赛事都可点开查看完整单打签表。",
             "Filter by status — all, ongoing or completed. Every event links to its complete singles draw.")}
  <div class="cal-scope">
    {anchors}
    <div class="sort-bar">
      <span class="sort-label">{bi("筛选", "Filter")}</span>
      <div class="chips">{chips}</div>
    </div>
    <div class="panel"><div class="cal-views">{"".join(views)}</div></div>
  </div>
</div>
'''
    return shell(ctx, title="赛程 · Tour Calendar", active="calendar.html", body=body)


def _month(month: str, english: bool = False) -> str:
    year, mon = month.split("-")
    return f"{MONTH_EN.get(mon, mon)} {year}" if english else f"{year} 年 {MONTH_ZH.get(mon, mon)}"


def _calendar_row(ctx: Context, event: dict, today: str) -> str:
    """One row of the calendar; linked when a draw is stored for the event."""
    key = event["path"].strip("/").split("/")
    slug = key[0] if key else ""
    year = event["year"]
    has_draw = any(e.get("path") == event["path"] for e in ctx.events.values())
    href = f"event-{slug}-{year}.html"

    if has_draw:
        name = f'<a class="tl-name-link" href="{href}">{ctx.tournament(event["name"])}</a>' + ctx.level_tag(event["level"])
        more = ('<a class="tl-more" href="' + href + '">'
                + bi(f'{event["matches"]} 场赛果', f'{event["matches"]} results') + " →</a>")
    else:
        name = ctx.tournament(event["name"]) + ctx.level_tag(event["level"])
        more = ""

    champion = event.get("champion")
    if champion:
        winner = ('<span class="tl-winner"><span class="cup" aria-hidden="true">🏆</span>'
                  + ctx.avatar(champion, 24)
                  + f'<a href="player-{champion["id"]}.html">{ctx.name(champion)}</a></span>')
    elif event["end"] < today:
        winner = f'<span class="tl-winner dim">{bi("未收录冠军", "No champion")}</span>'
    else:
        winner = f'<span class="tl-winner dim">{bi("待定", "TBD")}</span>'

    live = " live" if event["start"] <= today <= event["end"] else ""
    past = " past" if event["end"] < today else ""
    days_label = bi(f'{event["days"]} 天', f'{event["days"]} days')
    matches_label = bi(f'{event["matches"]} 场', f'{event["matches"]} matches')
    return (
        f'<div class="tl-item{past}{live}">'
        '<div class="tl-date">'
        f'<span class="tl-range">{esc(short_date(event["start"]))} – {esc(short_date(event["end"]))}</span>'
        f'<span class="tl-count">{days_label}</span></div>'
        f'<div class="tl-main"><div class="tl-name">{name}</div>'
        f'<div class="tl-meta">{ctx.surface_chip(event["surface"])}'
        f'<span>{matches_label}</span></div></div>'
        f'<div class="tl-side">{winner}{more}</div></div>'
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def results_page(ctx: Context) -> str:
    items = "".join(_result_row(ctx, r) for r in ctx.results)
    body = f'''
<div class="wrap">
  {page_head("Results · 比赛结果", "", "赛季比赛结果", "Season results",
             f'共 {num(len(ctx.results))} 场已收录赛果，按日期由新到旧。',
             f'{num(len(ctx.results))} matches captured, newest first.')}
  <div class="panel"><div class="result-list">{items
    or '<div class="empty-state">' + bi("暂无赛果", "No results yet") + "</div>"}</div></div>
</div>
'''
    return shell(ctx, title="赛果 · Results", active="results.html", body=body)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def stats_page(ctx: Context) -> str:
    cards = "".join(_leader_card(ctx, b) for b in ctx.boards)
    career = ctx.career
    body = f'''
<div class="wrap">
  {page_head(f"Season statistics · {ctx.season} 赛季数据", "", "每一项数据的领跑者",
             "Leaders across every measured statistic",
             "全部由官方发布的比赛结果统计得出：胜场、胜率、冠军数、各场地胜率与本周排名上升幅度。",
             "Counted from published results — wins, win rate, titles, per-surface win rate and this week's biggest climbers.")}
  <div class="leader-grid">{cards}</div>
  <div class="panel">
    <div class="panel-head"><h3>{bi("生涯领跑 · 单打冠军", "All-Time Leaders · Singles titles")}</h3>
      <span class="panel-note">{bi("现役排名球员中的历史累计", "All-time among currently ranked players")}</span></div>
    <div class="career-grid">
      {_career_col(ctx, "生涯单打冠军", "Career titles", career.get("titles", []), lambda p: num(p.get("main") or p.get("value")))}
      {_career_col(ctx, "生涯胜场", "Career match wins", career.get("careerWins", []), lambda p: num(p.get("value") or p.get("w")))}
      {_career_col(ctx, "生涯胜率", "Career win rate", career.get("careerPct", []), lambda p: pct(p.get("value")))}
    </div>
  </div>
</div>
'''
    return shell(ctx, title="数据 · Statistics", active="stats.html", body=body)


def _leader_card(ctx: Context, board: dict) -> str:
    top = board["rows"][0]["value"] if board["rows"] else 1
    rows = "".join(
        f'<div class="lb-row"><span class="i">{i + 1}</span>{ctx.avatar(ctx.player(r["id"]), 28)}'
        f'<span class="n"><b>{esc(r.get("zh") or r["name"])}</b>'
        f'<span class="en">{esc(r["name"])}</span></span>'
        f'<span class="v">{pct(r["value"]) if board["unit"] == "%" else num(r["value"])}</span>'
        f'<span class="lb-bar"><i style="width:{max(2, (r["value"] / top * 100) if top else 2):.1f}%"></i></span></div>'
        for i, r in enumerate(board["rows"][:10])
    )
    note = board.get("note") or ""
    note_html = f'<div class="card-bd dim" style="font-size:11.5px;border-top:1px solid rgba(255,255,255,.07)">{bi(note, "")}</div>' if note else ""
    detail = ""
    if board["key"] == "seasonWins" or board["key"] == "seasonWinPct":
        detail = ""
    return (
        f'<div class="leader-card"><div class="leader-head">'
        f'<h4>{bi(BOARD_ZH.get(board["key"], ""), board["label"])}</h4>'
        f'<span class="u">{esc("胜率" if board["unit"] == "%" else "总数")}</span></div>'
        f'<div class="leader-body">{rows}</div>{note_html}</div>'
    )


# ---------------------------------------------------------------------------
# Head-to-head
# ---------------------------------------------------------------------------

H2H_DEPTH = 50


# Mirrors SEP in fetch_h2h.py: ids can contain a dash, so "|" separates the pair.
def _pair_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


SEP = "|"


def _pair_options(ctx: Context, roster: list[dict], selected=None,
                  placeholder: str | None = None) -> str:
    """`<option>` 列表：snooker 式的「中文名 · 英文名（#rank）」标签。"""
    out: list[str] = []
    if placeholder is not None:
        out.append(f'<option value="" selected>{esc(placeholder)}</option>')
    for p in roster:
        zh_name = p.get("zh") or ""
        label = (f"{esc(zh_name)} · {esc(p['name'])}" if zh_name and zh_name != p["name"]
                 else esc(p["name"]))
        rank = f"（#{p['rank']}）" if p.get("rank") else ""
        sel = " selected" if selected is not None and str(p["id"]) == str(selected) else ""
        out.append(f'<option value="{esc(p["id"])}"{sel}>{label}{rank}</option>')
    return "".join(out)


def h2h_hub(ctx: Context, roster: list[dict]) -> str:
    """
    The comparison start page, in the snooker dashboard's shape: two native
    <select> controls — Player A and Player B — separated by "VS".  Picking both
    navigates to that pairing's page.

    The controls work because a small enhancer in the head reads the pair and
    jumps to the page; with scripting off the <noscript> block below carries the
    plain-link fallback, so the site remains fully usable either way.
    """
    # <noscript> 回退：无 JS 时新鲜的 details 双框照常可用。
    noscript_rows = "".join(
        f'<a class="h2h-pick-row" href="h2h-pick-{p["id"]}.html">'
        f'{ctx.avatar(p, 30)}'
        f'<span class="sn"><b>{esc(p.get("zh") or p["name"])}</b>'
        f'<span class="en">{esc(p["name"])}</span></span>'
        f'<span class="sr">#{p["rank"]} {esc(p["country"])}</span>'
        f'<span class="go" aria-hidden="true">→</span></a>'
        for p in roster
    )
    total = len(roster) * (len(roster) - 1) // 2
    body = f'''
<div class="wrap">
  {page_head("Head-to-head · 交手对比", "", "两位球员对比", "Compare two players",
             "在两侧下拉里各选一位球员，选完即进入两人的完整交手记录与数据对比。",
             "Pick player A and player B from the two selects; the record opens as soon as both are chosen.")}
  <div class="panel h2h-overflow"><div class="card-bd">
    <form class="h2h-composer" onsubmit="return h2hGo(this)">
      <div class="h2h-field">
        <span class="h2h-field-label">{bi("球员 A", "Player A")}</span>
        <select class="h2h-native" name="pa" onchange="h2hGo(this.form)">
          {_pair_options(ctx, roster, placeholder="选择球员 / Pick")}
        </select>
      </div>
      <div class="h2h-vs" aria-hidden="true">VS</div>
      <div class="h2h-field">
        <span class="h2h-field-label">{bi("球员 B", "Player B")}</span>
        <select class="h2h-native" name="pb" onchange="h2hGo(this.form)">
          {_pair_options(ctx, roster, placeholder="选择球员 / Pick")}
        </select>
      </div>
    </form>
    <noscript>
      <div class="h2h-fallback-note">{bi(
          "当前浏览器禁用了脚本，改用下列选择方式（也可从右侧菜单进入）：",
          "Scripting is off, so the link-list fallback is shown instead.")}</div>
      <div class="h2h-columns">
        <div><div class="h2h-col-head">{bi("球员一（前 50）", "Player one (top 50)")}</div>
          <div class="h2h-column">{noscript_rows}</div></div>
        <div><div class="h2h-col-head">{bi("球员二（前 50）", "Player two (top 50)")}</div>
          <div class="h2h-column">{noscript_rows}</div></div>
      </div>
    </noscript>
    <p class="dim mt4" style="font-size:12px">{bi(
      f"可对比范围为当前排名前 {len(roster)} 的球员，共生成 {num(total)} 组对阵页。",
      f"Comparisons cover the current top {len(roster)}, generating {num(total)} pairing pages.")}</p>
  </div></div>
</div>
'''
    return shell(ctx, title="交手 · Head-to-head", active="h2h.html", body=body, enhance=True)


def h2h_pick(ctx: Context, player: dict, opponents: list[dict]) -> str:
    """
    The second half of the snooker-style composer: Player A is fixed in the left
    box, and the right box is an openable opponent menu.  Player A's own box is
    still a live details control listing the whole roster, so switching "A" is
    one click away — matching the snooker dashboard, where both selects stay
    editable above the record.
    """
    def roster_rows():
        return "".join(
            f'<a class="h2h-pick-row" href="h2h-pick-{p["id"]}.html">'
            f'{ctx.avatar(p, 30)}'
            f'<span class="sn"><b>{esc(p.get("zh") or p["name"])}</b>'
            f'<span class="en">{esc(p["name"])}</span></span>'
            f'<span class="sr">#{p["rank"]} {esc(p["country"])}</span>'
            f'<span class="go" aria-hidden="true">→</span></a>'
            for p in ctx.pair_roster
        )
    opponent_menu = "".join(
        f'<a class="h2h-pick-row" href="h2h-{_pair_key(player["id"], o["id"]).replace(SEP, "-")}.html">'
        f'{ctx.avatar(o, 30)}'
        f'<span class="sn"><b>{esc(o.get("zh") or o["name"])}</b>'
        f'<span class="en">{esc(o["name"])}</span></span>'
        f'<span class="sr">{esc((f"#{o["rank"]} " if o.get("rank") else "") + (o.get("country") or ""))}</span>'
        f'<span class="go" aria-hidden="true">→</span></a>'
        for o in opponents
    )
    body = f'''
<div class="wrap">
  {page_head("Head-to-head · 交手对比", "", "两位球员对比", "Compare two players",
             "左侧已选出球员 A；从右侧菜单选择球员 B，即可查看两人的完整交手记录与数据对比。",
             "Player A is picked; open the menu on the right to choose player B.")}
  <div class="panel h2h-overflow"><div class="card-bd">
    <div class="h2h-composer">
      <div class="h2h-field">
        <span class="h2h-field-label">{bi("球员 A", "Player A")}</span>
        <details class="h2h-select">
          <summary>
            {ctx.avatar(player, 30)}
            <span class="sn"><b>{esc(player.get("zh") or player["name"])}</b>
              <span class="en">{esc(player["name"])}</span></span>
            <span class="sr">#{player["rank"]} {esc(player.get("country") or "")}</span>
            <span class="caret" aria-hidden="true">▾</span>
          </summary>
          <div class="h2h-menu">{roster_rows()}</div>
        </details>
      </div>
      <div class="h2h-vs" aria-hidden="true">VS</div>
      <div class="h2h-field">
        <span class="h2h-field-label">{bi("球员 B", "Player B")}</span>
        <details class="h2h-select">
          <summary><span class="ph">{bi("点击选择对手", "Pick the opponent")}</span>
            <span class="caret" aria-hidden="true">▾</span></summary>
          <div class="h2h-menu">{opponent_menu}</div>
        </details>
      </div>
    </div>
  </div></div>
</div>
'''
    return shell(ctx, title=f'{player.get("zh") or player["name"]} · 交手', active="h2h.html", body=body)


def h2h_pair(ctx: Context, a: dict, b: dict, record: dict | None, meetings: list) -> str:
    aw = (record or {}).get("aw", 0)
    bw = (record or {}).get("bw", 0)
    total = (record or {}).get("n", 0)
    share = (aw / (aw + bw) * 100) if (aw + bw) else 50

    cls_a = " lead" if aw > bw else " behind" if aw < bw else ""
    cls_b = " lead" if bw > aw else " behind" if bw < aw else ""
    rank_a = f'#{a["rank"]}' if a.get("rank") else ""
    rank_b = f'#{b["rank"]}' if b.get("rank") else ""

    def meeting_row(m):
        day, event, event_zh, score, winner_id = m[0], m[1], m[2], m[3], m[4]
        winner = ctx.player(winner_id)
        loser = b if winner_id == a["id"] else a
        return (
            f'<div class="h2h-row"><div class="h2h-date">{esc(short_date(day, True))}</div>'
            f'<div class="h2h-tour">'
            f'<span class="cn">{esc(winner.get("zh") or winner["name"])} 胜 {esc(loser.get("zh") or loser["name"])}</span>'
            f'<span class="en">{esc(winner["name"])} def. {esc(loser["name"])}</span>'
            f'<span class="meta-line">{ctx.tournament(event)} · {esc(score)}</span></div>'
            f'<div class="h2h-sc">{esc(score)}</div></div>'
        )

    meeting_rows = "".join(meeting_row(m) for m in meetings) if meetings else ""
    body = f'''
<div class="wrap">
  <div class="sec-hd" style="border-bottom:0">
    <div><span class="eyebrow">{bi("Head-to-head · 交手对比", "")}</span>
      <h2 style="font-size:clamp(22px,3vw,32px)">{ctx.name(a)} <em style="font-style:italic;color:var(--ivory-mute)">vs</em> {ctx.name(b)}</h2>
    </div>
    <a class="link" href="h2h.html">{bi("换一对球员", "Pick another pairing")} →</a>
  </div>
  <div class="panel"><div class="h2h-panel">
    <div class="h2h-summary">
      <div class="h2h-side{cls_a}">{ctx.avatar(a, 80)}{ctx.name(a)}
        <span class="meta">{rank_a} {esc(a.get("country") or "")}</span></div>
      <div class="h2h-score"><div class="ws">{aw} <span class="sep">–</span> {bw}</div>
        <small>{bi("交手记录", "head-to-head")}</small></div>
      <div class="h2h-side{cls_b}">{ctx.avatar(b, 80)}{ctx.name(b)}
        <span class="meta">{rank_b} {esc(b.get("country") or "")}</span></div>
    </div>
    <div class="h2h-bar"><i class="a" style="width:{share:.1f}%"></i><i class="b" style="width:{100 - share:.1f}%"></i></div>
    <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--ivory-mute);font-family:var(--font-cn)">
      <span>{esc(a.get("zh") or a["name"])} {aw} {bi("胜", "wins")}</span>
      <span>{esc(b.get("zh") or b["name"])} {bw} {bi("胜", "wins")}</span></div>
    {f'<div class="mp-sec"><h4>{bi(f"交手明细（{total} 场）", f"Meetings ({total})")}</h4>{meeting_rows}</div>'
     if meeting_rows else
     f'<div class="h2h-empty">{bi("这两位球员在已收录的赛果窗口内没有交手记录，双方仍可对比下方数据。", "These two have no meeting inside the stored results window; the comparison below still applies.")}</div>'}
    {_compare_block(ctx, a, b)}
  </div></div>
</div>
'''
    title = f'{a.get("zh") or a["name"]} vs {b.get("zh") or b["name"]}'
    return shell(ctx, title=f"{title} · 交手", active="h2h.html", body=body)


def _compare_block(ctx: Context, a: dict, b: dict) -> str:
    titles_a = (a.get("titles") or {}).get("main")
    titles_b = (b.get("titles") or {}).get("main")
    season_a = a.get("season") or {}
    season_b = b.get("season") or {}

    def row(zh, en, va, vb, better=None):
        fa = "—" if va in (None, "") else va
        fb = "—" if vb in (None, "") else vb
        wa = wb = ""
        if better and isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if better == "low":
                wa, wb = (" win" if va < vb else ""), (" win" if vb < va else "")
            else:
                wa, wb = (" win" if va > vb else ""), (" win" if vb > va else "")
        return (f'<div class="cmp-row"><span class="a{wa}">{fa}</span>'
                f'<span class="k">{bi(zh, en)}</span><span class="b{wb}">{fb}</span></div>')

    return (
        '<div class="h2h-compare mp-sec"><h4>' + bi("数据对比", "Statistical comparison") + "</h4>"
        + row("世界排名", "Ranking", a.get("rank"), b.get("rank"), "low")
        + row("排名积分", "Points", a.get("points"), b.get("points"), "high")
        + row("本周变动", "Weekly move", a.get("move"), b.get("move"), "high")
        + row(f"{ctx.season} 胜负", f"{ctx.season} W–L", _record(season_a.get("w"), season_a.get("l")),
              _record(season_b.get("w"), season_b.get("l")))
        + row("生涯单打冠军", "Career titles", titles_a, titles_b, "high")
        + row("生涯胜场", "Career wins", (a.get("career") or {}).get("w"), (b.get("career") or {}).get("w"), "high")
        + row("生涯胜率", "Career win rate",
              pct(_win_pct((a.get("career") or {}).get("w"), (a.get("career") or {}).get("l"))),
              pct(_win_pct((b.get("career") or {}).get("w"), (b.get("career") or {}).get("l"))))
        + row("最高排名", "Career high", a.get("highRank"), b.get("highRank"), "low")
        + row("身高", "Height", f'{a["height"]} cm' if a.get("height") else None,
              f'{b["height"]} cm' if b.get("height") else None, "high")
        + row("持拍", "Plays", a.get("hand"), b.get("hand"))
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Player profile
# ---------------------------------------------------------------------------


def player_page(ctx: Context, player: dict, rivals: list[dict], recent: list[dict]) -> str:
    """A full profile: biography, record by season, surface splits, titles, rivals, matches."""
    pid = player["id"]
    career = player.get("career") or {}
    by_surface = player.get("careerBySurface") or {}
    titles = player.get("titles") or {}
    season = player.get("season") or {}

    season_rows = "".join(
        f'<tr><td class="l num">{s["year"]}</td>'
        f'<td class="num dim">{(s.get("w") or 0) + (s.get("l") or 0)}</td>'
        f'<td class="num" style="color:var(--grass-400)">{s.get("w")}</td>'
        f'<td class="num" style="color:#e88a94">{s.get("l")}</td>'
        f'<td class="num">{pct(_win_pct(s.get("w"), s.get("l")))}</td></tr>'
        for s in (player.get("seasons") or [])
    )

    surface_rows = "".join(
        f'<div class="lb-row" style="grid-template-columns:minmax(0,1fr) auto auto">'
        f'<span class="lb-n dim" style="font-size:12.5px">{ctx.surface(name)}</span>'
        f'<span class="lb-v">{_record((split or {}).get("w"), (split or {}).get("l"))}</span>'
        f'<span class="lb-v">{pct(_win_pct((split or {}).get("w"), (split or {}).get("l")))}</span></div>'
        for name in ["Hard", "Clay", "Grass", "Indoors"]
        for split in [by_surface.get(name)]
        if split
    )

    title_rows = "".join(
        f'<div class="mini-row"><span class="n"><b>{t["year"]}</b></span>'
        f'<span class="v">{t["main"]}</span>'
        f'<span class="mini-bar" style="grid-column:1/-1">'
        f'{esc(" · ".join(t.get("events") or []))}</span></div>'
        for t in (titles.get("byYear") or [])[:10]
    )

    rival_rows = "".join(_rival_row(ctx, pid, r) for r in rivals)
    match_rows = "".join(_match_row(ctx, m) for m in recent)

    age = player.get("age")
    high = f'No.{player["highRank"]}' if player.get("highRank") else "—"
    meta_bits = [bi(f"世界第 {player['rank']}", f"World No.{player['rank']}"),
                 f'<span>{num(player["points"])} {bi("积分", "pts")}</span>']
    if age is not None:
        meta_bits.append(f'<span>{age} {bi("岁", "yrs")}</span>')
    if player.get("height"):
        meta_bits.append(f'<span>{player["height"]} cm</span>')
    if player.get("hand"):
        meta_bits.append(f'<span>{esc(player["hand"])}</span>')
    meta_bits.append(f'<span>{bi("最高排名", "Career high")} {high}</span>')

    titles_panel = ""
    if title_rows:
        titles_panel = (
            '<div class="panel mt5"><div class="panel-head">'
            f'<h3>{bi("冠军记录", "Titles by season")}</h3>'
            f'<span class="panel-note">{bi("主巡回赛冠军", "main-tour titles")}</span></div>'
            f'<div class="mini-boards">{title_rows}</div></div>'
        )
    rivals_panel = ""
    if rival_rows:
        rivals_panel = (
            '<div class="panel mt5"><div class="panel-head">'
            f'<h3>{bi("对现役前 30 的交手战绩", "Record against the current top 30")}</h3>'
            f'<span class="panel-note">{bi("已收录赛果", "stored results")}</span></div>'
            f'<div class="card-bd flush"><div class="rivals">{rival_rows}</div></div></div>'
        )

    body = f'''
<div class="wrap">
  <div class="sec-hd" style="border-bottom:0">
    <div><span class="eyebrow">{esc(ctx.zh.get("countries", {}).get(player["country"], player["country"]))}
      · {bi("单打", "Singles")}</span>
      <h2 style="font-size:clamp(26px,4vw,42px);letter-spacing:-0.03em">{ctx.name(player)}</h2>
      <div class="row wrap mt3" style="gap:14px;font-size:13px;color:var(--ivory-dim)">
        {"".join(meta_bits)}
      </div>
    </div>
    <a class="link" href="rankings.html">{bi("返回排名", "Back to rankings")} →</a>
  </div>

  <div class="tiles">
    <div class="tile"><b>{_record(season.get("w"), season.get("l"))}</b><small>{bi(f"{ctx.season} 胜负", f"{ctx.season} W–L")}</small></div>
    <div class="tile"><b>{num(titles.get("main"))}</b><small>{bi("生涯冠军", "Career titles")}</small></div>
    <div class="tile"><b>{_record(career.get("w"), career.get("l"))}</b><small>{bi("生涯胜负", "Career W–L")}</small></div>
    <div class="tile"><b>{pct(_win_pct(career.get("w"), career.get("l")))}</b><small>{bi("生涯胜率", "Career win rate")}</small></div>
    <div class="tile"><b>{num(titles.get("lower"))}</b><small>{bi("低级别冠军", "Lower-tier titles")}</small></div>
    <div class="tile"><b>{high}</b><small>{bi("最高排名", "Career high")}</small></div>
  </div>

  <div class="two-col mt5">
    <div class="panel">
      <div class="panel-head"><h3>{bi("分赛季战绩", "Record by season")}</h3></div>
      <div class="table-scroll"><table class="rank-table">
        <thead><tr><th class="l">{bi("赛季", "Season")}</th><th>{bi("场次", "Matches")}</th>
        <th>{bi("胜", "W")}</th><th>{bi("负", "L")}</th><th>{bi("胜率", "Win %")}</th></tr></thead>
        <tbody>{season_rows or f'<tr><td colspan="5">{bi("暂无赛季记录", "No season records")}</td></tr>'}</tbody>
      </table></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h3>{bi("生涯场地战绩", "Career record by surface")}</h3>
        <span class="panel-note">{bi("胜负 / 胜率", "W–L / win rate")}</span></div>
      <div class="card-bd">{surface_rows or '<div class="empty-state">' + bi("暂无数据", "No data") + "</div>"}</div>
    </div>
  </div>

  {titles_panel}

  {rivals_panel}

  <div class="panel mt5">
    <div class="panel-head"><h3>{bi("本赛季比赛记录", "This season's matches")}</h3>
      <span class="panel-note">{bi(f"最近 {len(recent)} 场", f"latest {len(recent)}")}</span></div>
    <div class="matches">{match_rows or '<div class="empty-state">' + bi("暂无比赛记录", "No match log stored") + "</div>"}</div>
  </div>
</div>
'''
    ld = {
        "@context": "https://schema.org",
        "@type": "Athlete",
        "name": player["name"],
        "alternateName": player.get("zh") or None,
        "nationality": player.get("country") or None,
        "birthDate": player.get("birth") or None,
        "height": ({"@type": "QuantitativeValue", "value": player["height"], "unitCode": "CMT"}
                   if player.get("height") else None),
        "sport": "Tennis",
        "jobTitle": "professional tennis player",
        "url": f'https://moonquake2004.github.io/atp-tour-dashboard/player-{pid}.html',
    }
    ld = {k: v for k, v in ld.items() if v is not None}
    return shell(ctx, title=player.get("zh") or player["name"], active="players.html",
                 body=body, description=f'{player["name"]} — 生涯战绩、场地胜率与交手记录。',
                 jsonld=ld)


def _rival_row(ctx: Context, pid: str, rival: dict) -> str:
    other = rival["player"]
    rank_mark = f'<span class="num dim r-rank">No.{other["rank"]}</span>' if other.get("rank") else ""
    record = (f'<span class="r-rec {"lead" if rival["wins"] > rival["losses"] else "trail" if rival["wins"] < rival["losses"] else ""}">'
              f'{rival["wins"]}–{rival["losses"]}</span>')
    inner = (f'{ctx.avatar(other, 34)}<span class="r-name">{ctx.name(other)}</span>'
             f'<span class="flag">{esc(other.get("country") or "")}</span>{rank_mark}{record}')
    if ctx.has_pair_page(pid, other["id"]):
        key = _pair_key(pid, other["id"])
        return f'<a class="rival" href="h2h-{key.replace(SEP, "-")}.html">{inner}</a>'
    return f'<span class="rival">{inner}</span>'


def _match_row(ctx: Context, m: dict) -> str:
    """
    One match of the season log.

    The results feed carries no round, and the surface is only known when the
    event's draw was fetched, so the sub-line joins whichever parts exist rather
    than printing empty separators.
    """
    opponent = ctx.player(m["oid"])
    rank = f'<span class="num dim" style="font-size:11px">No.{m["orank"]}</span>' if m.get("orank") else ""
    parts = [ctx.tournament(m["t"])]
    if m.get("svc"):
        parts.append(ctx.surface(m["svc"]))
    sub = '<span class="dot">·</span>'.join(parts)
    return (
        f'<div class="match"><span class="m-date">{esc(short_date(m["d"]))}</span>'
        f'<span class="m-res {"w" if m.get("w") else "l"}">{"W" if m.get("w") else "L"}</span>'
        f'<span class="m-main"><span class="m-t">'
        f'<a class="m-name" href="player-{m["oid"]}.html">{esc(opponent.get("zh") or m.get("o") or "")}</a>'
        f'<span class="flag">{esc(m.get("oc") or "")}</span>{rank}</span>'
        f'<span class="m-sub">{sub}</span>'
        f'</span><span class="m-score">{esc(m["sc"])}</span></div>'
    )


def player_page_light(ctx: Context, player: dict) -> str:
    """A compact profile for a player outside the ranking table."""
    rank_line = ""
    if player.get("rank"):
        rank_line = "<span>" + bi(f"世界第 {player['rank']}", f"World No.{player['rank']}") + "</span>"
    body = f'''
<div class="wrap">
  <div class="sec-hd" style="border-bottom:0">
    <div><span class="eyebrow">{esc(ctx.zh.get("countries", {}).get(player.get("country") or "", player.get("country") or ""))}</span>
      <h2 style="font-size:clamp(24px,3.4vw,38px)">{ctx.name(player)}</h2>
      <div class="row wrap mt3" style="gap:14px;font-size:13px;color:var(--ivory-dim)">{rank_line}</div>
    </div>
    <a class="link" href="players.html">{bi("返回球员名录", "Back to players")} →</a>
  </div>
  <p class="dim" style="font-size:12.5px">{bi(
    "这位球员不在当前单打排名表内，因此本站没有他的档案与赛季统计；他参加过的比赛仍收录在赛果中。",
    "This player is outside the current singles ranking, so no profile or season statistics are published here; their matches are still in the results.")}</p>
</div>
'''
    return shell(ctx, title=player.get("zh") or player["name"], active="players.html", body=body)


# ---------------------------------------------------------------------------
# Event draw
# ---------------------------------------------------------------------------


def event_page(ctx: Context, event: dict) -> str:
    """One event's complete singles draw."""
    rounds = event["rounds"]
    total = sum(len(r["matches"]) for r in rounds)
    slug = event["path"].strip("/").split("/")[0]

    final = next((r for r in rounds if r["code"] == "F"), None)
    champion = None
    if final and final["matches"]:
        champion = final["matches"][0]["winner"]

    round_links = "".join(
        f'<a class="seg" href="#r-{esc(r["code"])}">{ctx.round_(r["code"])}'
        f'<span class="ev-n">{len(r["matches"])}</span></a>'
        for r in rounds
    )

    def match_row(m):
        a, b = m["winner"], m["loser"]
        seed_a = f'<span class="ev-seed">{a["seed"]}</span>' if a.get("seed") else ""
        seed_b = f'<span class="ev-seed">{b["seed"]}</span>' if b.get("seed") else ""
        score = esc(" ".join(m.get("score") or []) or "—")
        return (
            '<div class="ev-match">'
            f'<div class="ev-side win">{seed_a}'
            f'<a class="ev-nm" href="player-{a["id"]}.html">{bi(ctx.h2h_players.get(a["id"], {}).get("zh"), a["name"])}</a></div>'
            f'<div class="ev-score">{score}</div>'
            f'<div class="ev-side b">{seed_b}'
            f'<a class="ev-nm" href="player-{b["id"]}.html">{bi(ctx.h2h_players.get(b["id"], {}).get("zh"), b["name"])}</a></div></div>'
        )

    def round_block(r):
        label = bi(f'{len(r["matches"])} 场', f'{len(r["matches"])} matches')
        return (
            f'<div class="ev-round" id="r-{esc(r["code"])}">'
            f'<div class="ev-round-head">{ctx.round_(r["code"])}'
            f'<span class="ev-round-n">{label}</span></div>'
            + "".join(match_row(m) for m in r["matches"])
            + "</div>"
        )

    draw = "".join(round_block(r) for r in rounds)

    champion_html = ""
    if champion:
        champion_html = ('<div class="ev-champ"><span class="cup" aria-hidden="true">🏆</span>'
                         + bi("冠军", "Champion") + " "
                         + f'<a href="player-{champion["id"]}.html">{ctx.name(ctx.player(champion["id"]))}</a></div>')

    dates = event.get("dates") or []
    span = f"{dates[0]} → {dates[-1]}" if dates else ""
    body = f'''
<div class="wrap">
  <div class="sec-hd" style="border-bottom:0">
    <div><span class="eyebrow">{ctx.level_tag(event.get("level"))} {ctx.surface_chip(event.get("surface"))}</span>
      <h2 style="font-size:clamp(22px,3.4vw,36px)">{ctx.tournament(event["name"])}</h2>
      <div class="row wrap mt3" style="gap:14px;font-size:12.5px;color:var(--ivory-dim)">
        <span>{esc(event["year"])}</span>
        {f"<span>{esc(span)}</span>" if span else ""}
        <span>{bi(f"{len(rounds)} 个轮次", f"{len(rounds)} rounds")}</span>
        {champion_html}
      </div>
    </div>
    <a class="link" href="calendar.html">{bi("返回赛程", "Back to calendar")} →</a>
  </div>
  <div class="panel"><div class="card-bd">
    <div class="ev-summary">
      <span>{bi(f"{total} 场单打", f"{total} singles matches")}</span>
      <span>{bi(f"{len(event.get('players') or {})} 位球员", f"{len(event.get('players') or {})} players")}</span>
    </div>
    <div class="ev-rounds seg-group">{round_links}</div>
    <div class="ev-list">{draw}</div>
  </div></div>
</div>
'''
    dates = event.get("dates") or []
    event_url = ('https://moonquake2004.github.io/atp-tour-dashboard/'
                 f'event-{event["path"].strip("/").split("/")[0]}-{event["year"]}.html')
    ld = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": event["name"],
        "sport": "Tennis",
        "startDate": (dates[0] if dates else "") or None,
        "endDate": (dates[-1] if dates else "") or None,
        "location": event.get("country") or event.get("flag") or None,
        "url": event_url,
    }
    ld = {k: v for k, v in ld.items() if v}
    return shell(ctx, title=f'{event["name"]} {event["year"]} · 赛果', active="calendar.html",
                 body=body, description=f'{event["name"]} {event["year"]} 完整单打签表。',
                 jsonld=ld)
