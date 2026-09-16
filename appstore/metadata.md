# App Store 上架文案

> 用于 App Store Connect 各字段。**所有名称都不含 ATP / WTA 商标**（5.2.1 要求）。

---

## 一、App 名称（Name，30 字符上限）

**候选（按推荐度）**

| 名称 | 字符数 | 备注 |
|---|---|---|
| `Baseline` | 8 | 球场基线，网球语汇，简短好记。**首选** |
| `Topspin` | 7 | 上旋球，直观 |
| `Deuce` | 5 | 平分，最短 |
| `Tour Tennis` | 11 | 描述性，偏泛 |
| `Centre Court` | 12 | 中央球场 |

⚠️ **名称可用性必须在 App Store Connect 里查重**（我无法查询 App Store）。
若首选被占用，依次尝试下一个。

**绝不可用的写法**（含他人商标）：
`ATP Dashboard` · `WTA Tour` · `ATP 排名` · `WTA 数据看板` —— 任何以商标为主体的名称。

**相对安全的措辞**：在**描述正文**中作事实性指称（如"覆盖 ATP 巡回赛赛程与赛果"）
通常可接受，但**不能出现在名称、副标题、图标或关键词字段里抢占商标**。
最终判断请咨询专业人士。

---

## 二、副标题（Subtitle，30 字符上限）

```
赛程 · 排名 · 赛果 · 交手记录
```
```
Rankings, draws and head-to-heads
```
```
职业网球数据，离线可用
```

---

## 三、关键词（Keywords，100 字符上限，逗号分隔，无空格）

```
tennis,ranking,draw,results,atp,tour,score,h2h,match,statistics,球员,排名,赛程,赛果,交手,网球
```

> 说明：把 `atp` 放进关键词字段属于灰色地带——**建议先不放**，避免 5.2.1 争议。
> 上面这串保留 `atp` 仅作备选，正式提交前请删掉它。

---

## 四、描述（Description，4000 字符上限）

### 中文

```
一款为网球球迷做的数据看板：排名、赛程、赛果、球员档案与历史交手，全部离线可用。

■ 世界排名
官方单打世界排名，含名次升降与积分变化；可按积分、姓名、年龄或本周变动排序。

■ 赛程与赛果
整个赛季的赛事日历，标注场地类型、奖金与冠军。每站赛事都能点开查看完整单打签表，
按轮次逐场呈现，含种子与比分。

■ 球员档案
每位排名球员的档案：身高、年龄、持拍手、最高排名、生涯胜负、
分赛季战绩、各场地胜率、冠军记录与本赛季全部比赛。

■ 交手记录
任意两位球员的完整交手记录与逐项数据对比。

■ 球员名录
全部排名球员卡片式浏览，可按国家筛选。

■ 为什么离线
所有数据随 app 一起打包，没有网络也能查看排名、赛程与历史赛果。
联网时自动获取最新数据。

■ 关于我们
独立开源项目。没有账号，没有广告，不收集任何个人数据。
```

### English

```
A data dashboard for tennis fans: rankings, calendar, results, player profiles and
career head-to-heads — all available offline.

■ WORLD RANKINGS
The official singles ranking with weekly movement and points. Sort by points, name,
age or this week's biggest risers.

■ CALENDAR & RESULTS
The whole season's calendar with surface, prize money and champion. Every event
opens into its complete singles draw, round by round, with seeds and scores.

■ PLAYER PROFILES
Each ranked player's profile: height, age, handedness, career-high ranking, career
win/loss, season-by-season record, per-surface win rate, titles and the season's
matches.

■ HEAD-TO-HEAD
Any two players' complete record against each other, with a side-by-side
statistical comparison.

■ PLAYER DIRECTORY
Every ranked player as a card, filterable by country.

■ WHY OFFLINE
The data ships inside the app, so rankings, calendar and past results are
available without a connection. It refreshes when you are online.

■ ABOUT
An independent open-source project. No accounts, no advertising, and no personal
data collected.
```

---

## 五、其他字段

| 字段 | 内容 |
|---|---|
| **推广文本**（Promotional Text，170 字符） | `新赛季数据已更新：最新排名、完整赛程与全部赛果。离线可用，无广告，不收集个人数据。` |
| **分类**（Category） | 主：体育（Sports）　次：参考资料（Reference） |
| **年龄分级** | 4+（无暴力、无成人内容、无用户生成内容） |
| **价格** | 待定（免费 / 付费由你决定；**注意数据授权成本需覆盖**） |
| **隐私政策 URL** | 发布 `privacy-policy.html` 后的 HTTPS 地址 |
| **技术支持 URL** | 建议用仓库的 Issues 页：`https://github.com/moonquake2004/<repo>/issues` |
| **版权** | `© 2026 <你的名字或主体>`（**不要写 ATP/WTA**） |

---

## 六、App Privacy 问卷（App Store Connect）

按当前设计（无账号、无分析、无广告）如实填写：

| 问题 | 回答 |
|---|---|
| 是否收集数据？ | **否**（Data Not Collected） |
| 是否使用第三方 SDK 收集？ | 否 |
| 是否用于追踪（Tracking）？ | 否 |

⚠️ 一旦以后加入任何分析／崩溃上报 SDK，**此问卷与隐私政策必须同步修改**。

---

## 七、截图要求

App Store 至少需要一组 iPhone 截图。常见尺寸（**提交前请在 App Store Connect 确认当前要求**）：

| 设备 | 像素 |
|---|---|
| iPhone 6.9"（16 Pro Max） | 1320 × 2868 |
| iPhone 6.7"（14/15 Pro Max） | 1290 × 2796 |
| iPad 13" | 2064 × 2752 |

已生成的草稿见 `screenshots/`。**这些是从网页版截取的，正式提交前需从真实 app 重新截取**
（`scripts/shots.mjs` 可复用，改一行 URL 即可）。

建议顺序（3–6 张已足够）：
1. 总览（英雄区 + 赛季 KPI）
2. 排名（领奖台 + 榜单）
3. 球员档案（数据块 + 分赛季战绩）
4. 赛程（按状态筛选）
5. 交手对比
6. 赛事签表

---

## 八、提交前检查

- [ ] 名称已查重，且不含 ATP / WTA
- [ ] 关键词里已删掉 `atp`
- [ ] 隐私政策已发布到 HTTPS，URL 已填入且 app 内可访问
- [ ] 技术支持 URL 可访问
- [ ] App Privacy 问卷与隐私政策一致
- [ ] 截图从真实 app 截取、尺寸正确
- [ ] 图标 1024×1024，**不含任何 ATP/WTA 标志**
- [ ] 数据授权已到位（**没有这一项就不要提交**）
- [ ] 审核备注里说明数据来源与授权依据
