"""
Page templates for the generated site.

Each function returns a complete HTML document.  Nothing here runs in a browser:
the panels, tables, player pages and event pages are all written out at build
time, and the only client-side code is a four-line image fallback.
"""

from __future__ import annotations

import json

from render import (
    Context,
    bi,
    esc,
    iso_date,
    money,
    money_short,
    num,
    pct,
    short_date,
    timestamp,
)

NAV = [
    ("index.html", "总览", "Overview"),
    ("calendar.html", "赛程", "Calendar"),
    ("results.html", "赛果", "Results"),
    ("rankings.html", "排名", "Rankings"),
    ("players.html", "球员", "Players"),
    ("stats.html", "数据", "Statistics"),
    ("h2h.html", "交手", "Head-to-head"),
]

FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='13' fill='%230b2a1e'/%3E"
    "%3Ccircle cx='32' cy='32' r='19' fill='%23d8e63c'/%3E"
    "%3Cpath d='M14 26 Q32 33 50 26' stroke='%23fff' stroke-width='3.2' fill='none'/%3E"
    "%3Cpath d='M14 38 Q32 31 50 38' stroke='%23fff' stroke-width='3.2' fill='none'/%3E%3C/svg%3E"
)


def shell(ctx: Context, *, title: str, active: str, body: str, description: str = "") -> str:
    """
    Wrap a page body in the shared document.

    The three language anchors come first and are siblings of `.lang-ctx`, which
    is what lets `:target` drive the bilingual switch with no script.
    """
    season = ctx.season
    nav = "".join(
        f'<a class="nav-link{" active" if href == active else ""}" href="{href}">'
        f'<span class="cn">{cn}</span><span class="en">{en}</span></a>'
        for href, cn, en in NAV
    )
    desc = description or (
        f"{season} 赛季女子网球巡回赛数据看板：官方单打世界排名、赛程赛果、球员数据与历史交手记录。"
        "Official WTA rankings, calendar, results, player records and head-to-heads."
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)} | 女子网球巡回赛数据看板</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#0f4832">
<meta name="color-scheme" content="dark">
<meta name="author" content="WTA Tour Dashboard contributors">
<meta name="robots" content="index, follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)} | 女子网球巡回赛数据看板">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="assets/og-cover.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta property="og:locale:alternate" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="https://moonquake2004.github.io/wta-tour-dashboard/{active}">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@500;700;900&family=Oswald:wght@400;500;600;700&family=Barlow+Condensed:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/css/style.css">
</head>
<body>

<!-- 语言锚点：正文是它们的兄弟节点，因此 :target 可以控制 .cn/.en 的显隐 -->
<div id="lang-both" class="lang-anchor"></div>
<div id="lang-cn" class="lang-anchor"></div>
<div id="lang-en" class="lang-anchor"></div>

<div class="lang-ctx">
<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="index.html">
      <span class="brand-ball" aria-hidden="true"></span>
      <span class="brand-text">
        <strong class="brand-cn">女子网球巡回赛 · 数据看板</strong>
        <span class="brand-en">WTA TOUR · DATA DASHBOARD</span>
      </span>
    </a>
    <div class="season-chip">
      <span class="season-label"><i class="cn">赛季</i><i class="en">SEASON</i></span>
      <span class="season-value">{esc(season)}</span>
    </div>
    <div class="lang-switch">
      <a class="lang-btn" data-l="both" href="#lang-both"><span class="cn">双语</span><span class="en">BOTH</span></a>
      <a class="lang-btn" data-l="cn" href="#lang-cn"><span class="cn">中文</span><span class="en">CN</span></a>
      <a class="lang-btn" data-l="en" href="#lang-en"><span class="cn">英文</span><span class="en">EN</span></a>
    </div>
  </div>
  <nav class="main-nav">{nav}</nav>
</header>

<main>
{body}
</main>

<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <span class="brand-ball small" aria-hidden="true"></span>
      <div>
        <strong>{bi("女子网球巡回赛 · 数据看板", "WTA Tour Data Dashboard")}</strong>
        <p class="footer-note">{bi(
            "独立开源项目，与 WTA 无隶属关系。球员数据版权归 WTA Tour, Inc. 所有。",
            "An independent open-source project, not affiliated with the WTA. Player data © WTA Tour, Inc.",
        )}</p>
      </div>
    </div>
    <div class="footer-row">{footer_stats(ctx)}</div>
    <div class="footer-bar">
      <span>{bi("数据来源", "Source")}
        <a href="https://www.wtatennis.com/" target="_blank" rel="noopener">wtatennis.com</a></span>
      <span>{bi("最后更新", "Last updated")} <b>{esc(timestamp(ctx.meta.get("generatedAt")))}</b></span>
      <a class="footer-gh" href="https://github.com/moonquake2004/wta-tour-dashboard" target="_blank" rel="noopener">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.4 7.4 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>
        <span class="en">GitHub</span>
      </a>
    </div>
  </div>
</footer>
</div><!-- /lang-ctx -->
</body>
</html>
"""


def footer_stats(ctx: Context) -> str:
    c = ctx.counts
    items = [
        ("排名球员", "Players", num(c.get("rankedPlayers"))),
        ("赛季赛事", "Events", num(c.get("events"))),
        ("赛季比赛", "Matches", num(c.get("seasonMatches"))),
        ("交手配对", "H2H pairs", num(c.get("h2hPairings"))),
        ("收录赛事", "Calendar", num(c.get("calendarEvents"))),
    ]
    return "".join(
        f'<div class="f"><b>{esc(v)}</b><span>{bi(cn, en)}</span></div>' for cn, en, v in items
    )


# ---------------------------------------------------------------------------
# Shared fragments
# ---------------------------------------------------------------------------


def avatar(ctx: Context, player, size: int = 34, cls: str = "") -> str:
    return ctx.avatar(player, size, cls)


def player_cell(ctx: Context, player, size: int = 32, country: bool = True) -> str:
    meta = ""
    if country and player.get("country"):
        meta = f'<div class="row" style="gap:7px;margin-top:2px">{ctx.country(player["country"])}</div>'
    return (
        f'<div class="p-cell">{avatar(ctx, player, size)}'
        f'<div style="min-width:0">'
        f'<a class="p-name" href="player-{player["id"]}.html">{ctx.name(player)}</a>'
        f"{meta}</div></div>"
    )


def top_nav(prefix: str = "") -> str:
    """Language links that also carry the current fragment, so a choice sticks."""
    return ""


def page_head(eyebrow_zh, eyebrow_en, title_zh, title_en, sub_zh="", sub_en="") -> str:
    sub = ""
    if sub_zh or sub_en:
        sub = f'<p class="muted" style="margin:10px 0 0;max-width:78ch">{bi(sub_zh, sub_en)}</p>'
    return (
        '<div class="sec-hd" style="border-bottom:0;margin-bottom:var(--sp-5);align-items:flex-end">'
        f'<div><span class="eyebrow">{bi(eyebrow_zh, eyebrow_en)}</span>'
        f'<h2 style="font-size:clamp(26px,3.6vw,38px);letter-spacing:-0.03em">{bi(title_zh, title_en)}</h2>'
        f"{sub}</div></div>"
    )


def stat_card(label_zh, label_en, value, sub_html="") -> str:
    return (
        '<div class="card"><div class="card-bd">'
        f'<div class="eyebrow">{bi(label_zh, label_en)}</div>'
        f'<b class="num" style="display:block;font-size:30px;font-weight:500;'
        f'letter-spacing:-0.035em;margin-top:4px">{esc(value)}</b>'
        f'<div class="dim" style="font-size:12.5px">{sub_html}</div>'
        "</div></div>"
    )
