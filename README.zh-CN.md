# ATP 男子网球巡回赛 · 数据看板

**在线访问：** <https://moonquake2004.github.io/atp-tour-dashboard/>

一个独立、开源的 **中英双语** ATP 男子网球数据看板——单打世界排名、赛季赛程、
完整赛果、球员档案、各场地胜率、生涯数据榜与历史交手记录。

**全部用 Python 标准库实现**：无第三方依赖、无 JavaScript 框架、无构建工具。

---

## 这是什么

网站是**预渲染的**：构建时由 Python 写出 8,600+ 个完整 HTML 页面。
七个板块、300 个排名球员档案、248 个赛事签表都是静态文档，
**关闭 JavaScript 后整站可用**——输出里一个 `<script>` 标签都没有。

| 页面 | English | 内容 |
| --- | --- | --- |
| `index.html` | 总览 | 赛季 KPI、冠军墙、最新赛果、世界前十、赛季与生涯领跑 |
| `calendar.html` | 赛程 | 全部赛事：场地、奖金、场次、冠军；可按状态筛选 |
| `results.html` | 赛果 | 本赛季已结束比赛，由新到旧 |
| `rankings.html` | 排名 | 官方单打排名、领奖台、名次变动、预渲染的多种排序 |
| `players.html` | 球员 | 全部排名球员卡片，按国家筛选 |
| `player-<id>.html` | 球员档案 | 档案、分赛季战绩、生涯分场地战绩、冠军、对手、比赛记录 |
| `stats.html` | 数据 | 9 个榜单 + 生涯领跑 |
| `h2h.html` / `h2h-pick-<id>.html` | 交手 | 两步选择：先选球员，再选对手 |
| `h2h-<a>-<b>.html` | 交手对比 | 交手记录、逐场明细、逐项数据对比 |
| `event-<slug>-<year>.html` | 赛事签表 | 完整单打签表，按轮次排列 |

**不用 JavaScript 的交互**：语言切换、赛程状态筛选、排名排序、交手流程全部由
CSS `:target` 驱动。三个锚点位于 `<body>` 顶部、与正文同级，因此
`#lang-cn:target ~ .lang-ctx .en { display: none }` 仅靠 URL 片段即可切换语言。
球员头像缺失时由纯 CSS 字母层兜底。

---

## 数据来源

**ATP 官网无法使用**：`www.atptour.com` 对所有请求返回 `403`（Cloudflare 挑战页），
脚本浏览器也穿不过去；且没有公开 JSON 接口（`api.atptour.com` 无 DNS 记录）。
本看板改用两个转载官方数据的权威来源：

| 来源 | 用途 | 说明 |
| --- | --- | --- |
| **Tennis Explorer** | 排名、完整赛果、赛事签表、球员档案 | `robots.txt` 只禁 `/redirect/`、`/terms-of-use/`、`/contact/` |
| **Tennis Abstract**（Jeff Sackmann） | 官方排名交叉校验、Elo 评分 | 其 `/jsplayers/`、`/jsmatches/` **被 robots 禁止，刻意不抓取** |
| **Wikidata** | 球员中文名（属性 **P536** = ATP 球员 ID） | 按姓名匹配后转简体 |

### 决定了架构的五个约束

1. **逐日赛果页不含场地、也没有轮次**——场地与奖金只出现在赛事页头部
   （`(74,292,561 €, grass, men)`），轮次只在签表里，两者都要回填。
2. **比赛是成对的行**：每场两行共享 id 词干（`s10` / `s10b`），
   **id 不带 `b` 后缀的是胜者行**。看起来像胜者标记的 `fRow` class 只出现在部分行，
   而 `<strong>` 标记的是**本页球员**而非胜者。
3. **球员 slug 形态不统一**：多数是 `<姓名>-<hash>`，但也有纯姓名、复姓、
   以及以空段结尾的——所以用**完整 slug 作 id**，否则 `reis-da-silva` 与
   `dutra-da-silva` 会撞成同一个 `da-silva`。
4. **响应偶发截断**（`IncompleteRead`）：HTTP 层用 `http.client` 分块读取并在
   失败后回退到 `curl`；没有这层兜底，300 人的抓取会静默丢掉若干记录。
5. **源站不发布发球统计**（ACE、双误、一发成功率）。本站不去估算，
   而是改用官方确实发布的内容重建数据面板：胜场、胜率、冠军数、
   **各场地胜率**与本周排名上升幅度。

### 中文数据

| 数据 | 来源 |
| --- | --- |
| 球员中文名 | **Wikidata P536**，按折叠词元集合匹配（忽略姓名顺序、重音、连字符） |
| 繁→简 | **MediaWiki `zh-hans` 变体转换器** |
| 国家、巡回赛、轮次、场地、级别 | 人工术语表 |
| 挑战赛举办城市 | **Wikidata**（限定为"城市"类实体） |
| 少数排名球员 | 按各语言译音规范人工校订 |

仍未匹配的一律回退英文原名，不做猜测。

---

## 本地开发

需要 **Python 3.11+**，无需安装任何包。

```bash
python3 pyscripts/generate_data.py
python3 pyscripts/build_site.py
python3 pyscripts/serve.py            # http://127.0.0.1:4174
```

### 刷新数据

```bash
python3 pyscripts/build.py                  # 全量：排名 + 300 份档案 + 259 天赛果 + 全部签表
python3 pyscripts/refresh_rankings.py       # 每周轻量刷新
python3 pyscripts/verify.py && python3 pyscripts/verify_dashboard.py && python3 pyscripts/check_links.py
```

每个抓取步骤都支持**断点续抓**，网络中断后重跑即可补齐。
抓取器保持克制：2 个并发、1.1 秒间隔、指数退避——请沿用默认值。

---

## 数据口径说明

- **排名周期**：ATP 每周一发布；站内日期即该快照所属的那一周。
- **名次变动**：与官方表中"相比上周"完全一致。
- **赛季胜负**：由官方赛果统计。校验脚本会把**两个独立抓取的来源**做交叉比对
  ——每日赛果汇总出的胜负 vs 球员页自己的胜负表——并要求二者一致。
- **场地**：取自各赛事自己的页头，这是源站唯一声明场地的地方。
- **冠军**：取自球员页的冠军表，区分主巡回赛与低级别。
- **表演赛**：源站把表演赛与巡回赛混排，本站从赛程中排除
  （它们全年零散进行，按赛事聚合会横跨数百天）。
- **赛程只到本周**：源站日历不发布未来赛事，因此没有"未开始"筛选。

## 许可与署名

- **代码**：MIT，见 [LICENSE](LICENSE)。
- **数据**：不在 MIT 许可范围内。排名、赛果、签表与球员档案转载自
  **Tennis Explorer** 与 **Tennis Abstract**，原始来源为 **ATP**，
  以署名方式用于非商业信息目的。中文名来自 **Wikidata**（CC0）。
  球员头像直接从源站图片服务器加载，本项目不再分发。

本站与 ATP **无隶属关系**。权威信息请以 [atptour.com](https://www.atptour.com) 为准。
