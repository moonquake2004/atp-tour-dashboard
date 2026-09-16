# ATP Tour Data Dashboard · ATP 男子网球巡回赛数据看板

**Live:** <https://moonquake2004.github.io/atp-tour-dashboard/>

An independent, open-source, **bilingual (English / 简体中文)** data dashboard for
the **ATP Tour** — singles world ranking, the season calendar, complete results,
player profiles, per-surface win rates, career leaders and head-to-head records.

Built entirely with the **Python standard library** — no third-party packages, no
JavaScript framework, no build tooling.

---

## What it is

The site is **pre-rendered, not client-rendered**: Python writes thousands of
complete HTML pages at build time. Every panel, every ranked player's profile and
every event draw is a static document, and the site works with **JavaScript
switched off** — the output contains no `<script>` tag at all.

| Page | 中文 | Contents |
| --- | --- | --- |
| `index.html` | 总览 | Season KPIs, champion wall, latest results, top 10, season and career leaders |
| `calendar.html` | 赛程 | Every event with surface, prize money, match count and champion — filterable by status |
| `results.html` | 赛果 | The season's completed matches, newest first |
| `rankings.html` | 排名 | Official singles ranking, podium, movement, pre-rendered sort orders |
| `players.html` | 球员 | Every ranked player as a card, grouped by country |
| `player-<id>.html` | 球员档案 | Biography, record by season, career surface splits, titles, rivals, match log |
| `stats.html` | 数据 | Nine leaderboards plus career leaders |
| `h2h.html` | 交手 | Pairing hub — step one, pick a player from the top 50 |
| `h2h-pick-<id>.html` | 交手 | Step two — pick that player's opponent |
| `h2h-<a>-<b>.html` | 交手对比 | Career record, every meeting, side-by-side comparison |
| `event-<slug>-<year>.html` | 赛事签表 | The complete singles draw, round by round |

**Interaction without JavaScript.** Language switching, the calendar's status
filters, the ranking sort orders and the head-to-head flow are all driven by CSS
`:target`. Three anchors sit at the top of `<body>` and are siblings of the page
content, so `#lang-cn:target ~ .lang-ctx .en { display: none }` swaps the language
by URL fragment alone. Player portraits fall back to a CSS monogram layer, so a
missing photo never shows a broken icon.

---

## Data sources

**ATP's own site could not be used.** `www.atptour.com` answers every request with
`HTTP 403` behind a Cloudflare challenge — a plain `curl` and a scripted browser
both fail — and there is no public JSON API (`api.atptour.com` does not resolve).
Unlike the WTA, whose public feed powers the companion project, the ATP publishes
nothing an automated build can read.

This dashboard is therefore built from two sources that republish the official
data, both verified current at build time:

| Source | Used for | Notes |
| --- | --- | --- |
| **Tennis Explorer** | Rankings, complete results, event draws, player records | `robots.txt` permits everything read here (it excludes only `/redirect/`, `/terms-of-use/` and `/contact/`) |
| **Tennis Abstract** (Jeff Sackmann) | Official ranking cross-reference, Elo ratings | Its `/jsplayers/` and `/jsmatches/` paths are **disallowed by robots.txt** and are deliberately never requested |
| **Wikidata** | Chinese player names (property **P536** = ATP player id) | Matched by name, then normalised to Simplified Chinese |

### What each page contributes

| Page | Fields taken |
| --- | --- |
| `/ranking/atp-men/?page=N` | Rank, movement, name, country, points (50 per page) |
| `/results/?type=atp-single&year=&month=&day=` | Every completed match of the day, grouped under its event |
| `/<slug>/<year>/atp-men/` | Complete draw with round codes and titles; surface and prize money from the event header |
| `/player/<slug>/` | Country, height/weight, age and birthdate, handedness, career-high rank, W/L by season and surface, titles by season, portrait |

### Constraints that shaped the design

1. **The daily listing carries no surface and no round.** Surface and prize money
   appear only in an event's own header (`(74,292,561 €, grass, men)`), and the
   round appears only in the draw, so both are merged back into the calendar.
2. **Match rows are pairs.** Each match is two `<tr>` elements sharing an id stem
   (`s10` and `s10b`); the winner is the row whose id does *not* end in `b`. The
   `fRow` class that looks like a winner marker only appears on some rows, and the
   `<strong>` tag marks *the page's own player*, not the winner.
3. **Player slugs are not uniform.** Most are `<name>-<hash>` but some are a bare
   name, some carry a multi-part surname, and some end in an empty segment — so
   the **full slug** is the player id, because taking the last dash segment makes
   `reis-da-silva` and `dutra-da-silva` collide.
4. **Responses are occasionally truncated** (`IncompleteRead`). The HTTP layer
   reads in chunks over `http.client` and falls back to `curl`; without it a
   300-player run silently loses a handful of records.
5. **The source publishes no serve statistics** — no aces, double faults or
   first-serve percentages. Rather than invent them, the statistics panel is built
   from what the tour does publish: wins, win rate, titles, per-surface win rates
   and weekly ranking movement.

### Chinese localisation

| Dataset | Source |
| --- | --- |
| Player names | **Wikidata P536**, matched by folded token set so name order, accents and hyphens do not matter |
| Traditional → Simplified | **MediaWiki `zh-hans` variant converter** |
| Countries, tour events, rounds, surfaces, levels | Curated terminology tables |
| Challenger host cities | **Wikidata**, restricted to items that are actually cities |
| A minority of ranked players | Curated transliterations following each source language's conventions |

Anything still unmatched falls back to the English name rather than showing a
guess.

---

## Project layout

```
atp-dashboard/
├── pyscripts/                    Python pipeline (standard library only)
│   ├── wtalib.py                 HTTP client, politeness gate, TLS discovery, file helpers
│   ├── te.py                     Tennis Explorer client and every page parser
│   ├── atp_terms.py              Chinese terminology and curated transliterations
│   ├── fetch_rankings.py         official singles ranking
│   ├── fetch_players.py          biographies, season records, titles
│   ├── fetch_results.py          day-by-day crawl → calendar + complete results
│   ├── fetch_events.py           complete per-event draws
│   ├── fetch_h2h.py              folds results into a pairwise index
│   ├── fetch_zh.py               Chinese names (Wikidata + variant conversion)
│   ├── derive.py                 leaderboards, and surface backfill from draws
│   ├── generate_data.py          → data/atp.js, atp-events.js, atp-h2h*.js
│   ├── render.py                 formatting and bilingual primitives
│   ├── templates.py              document shell, header, footer
│   ├── pages.py                  the seven panels and the detail page kinds
│   ├── build_site.py             → docs/ (pre-rendered pages + SEO files)
│   ├── verify.py                 snapshot integrity, incl. a W/L cross-check
│   ├── verify_dashboard.py       payload integrity
│   ├── check_links.py            verifies every internal link resolves
│   ├── build.py                  full refresh orchestrator
│   ├── refresh_rankings.py       light weekly refresh
│   └── serve.py                  threaded preview server
├── site-py/assets/               stylesheet and social card
├── data/                         generated snapshots (committed)
└── docs/                         generated site (served by GitHub Pages)
```

---

## Local development

Requires **Python 3.11+**. No packages to install.

```bash
# regenerate the payload and the site
python3 pyscripts/generate_data.py
python3 pyscripts/build_site.py

# preview (threaded; a page requests hundreds of portraits)
python3 pyscripts/serve.py            # http://127.0.0.1:4174
```

### Refreshing data

```bash
# full refresh: rankings, 300 player records, 259 days of results, every draw
python3 pyscripts/build.py

# light weekly refresh: rankings → draws → derived → names → payload → site → verify
python3 pyscripts/refresh_rankings.py

# verify only
python3 pyscripts/verify.py && python3 pyscripts/verify_dashboard.py && python3 pyscripts/check_links.py
```

Every fetch step supports **resuming**: records already stored are not re-fetched,
so a run interrupted by a network hiccup can simply be repeated.

Environment variables: `ATP_RANK_DEPTH` (300), `ATP_PLAYER_LIMIT` (300),
`ATP_MATCH_SEASONS` (4), `ATP_RESULT_SEASONS` (2), `ATP_EVENT_LIMIT` (400),
`ATP_RESULT_LIMIT` (1500), `ATP_H2H_MAX` (24), `ATP_PLAYER_WORKERS` (2),
`ATP_EVENT_WORKERS` (2).

The fetcher is deliberately polite: two concurrent requests with a 1.1-second
spacing gate and exponential backoff. Please keep the defaults modest.

---

## Deploying

Published with **GitHub Pages** from the `docs/` folder:

1. `python3 pyscripts/build_site.py` regenerates `docs/`.
2. Commit and push to the default branch.
3. **Settings → Pages** → *Deploy from a branch* → `main` / `/docs`.

`.github/workflows/refresh.yml` refreshes the rankings every Monday, when the ATP
publishes its new list.

---

## Interpretation notes

- **Ranking weeks.** The ATP publishes rankings on Mondays; the date shown is the
  week the snapshot belongs to.
- **Movement.** The arrow compares this week with the previous published week,
  exactly as the ranking table reports it.
- **Season W–L.** Counted from the official results. The verification suite
  cross-checks it against the win/loss table on each player's own page — two
  independently scraped sources — and requires them to agree.
- **Surface.** Taken from each event's own header, which is the only place the
  source states it. A handful of exhibition series publish no surface.
- **Titles.** Counted from the title table on each player's page, split into main
  tour and lower level.
- **Exhibitions.** The source lists exhibition and training series alongside tour
  events. They are excluded from the calendar, because they run intermittently all
  season and a "tournament" built from them would span hundreds of days.

## Licence and attribution

- **Code:** MIT — see [LICENSE](LICENSE).
- **Data:** not covered by the MIT licence. Rankings, results, draws and player
  records are republished from **Tennis Explorer** and **Tennis Abstract**, and
  ultimately originate with the **ATP**. Used here for non-commercial
  informational purposes with attribution. Chinese names come from **Wikidata**
  (CC0). Player portraits are loaded directly from the source's image host and are
  not redistributed.

This project is **not affiliated with the ATP**. For authoritative information
always consult [atptour.com](https://www.atptour.com).
