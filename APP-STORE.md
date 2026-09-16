# 上架 App Store 的完整清单

> 目标：把本站做成 iOS app 并**正式上架 App Store**。
> 本文把「你必须决定/办理的事」与「我可以直接做的事」分开，并按执行顺序排列。
> 所有苹果条款均引自官方审核指南原文（已核实，非凭印象）。
>
> **我不是律师。** 下面关于授权与商标的部分是把苹果的要求原文引给你，
> 并列出可选路径；具体授权谈判请咨询专业人士。

---

## 一、结论先行

**技术上毫无障碍**，障碍全在两处：

| 门槛 | 严重程度 | 能否由我解决 |
|---|---|---|
| 4.2 最低功能性（不能只是"重新包装的网站"） | 中 —— 可以跨过 | ✅ 我能做 |
| **5.2 / 5.2.1 知识产权（数据与商标授权）** | **高 —— 硬伤** | ❌ 只有你能解决 |

**数据授权不解决，不要提交审核。** 苹果原文：

> Make sure your app **only includes content that you created or that you have a license to use**.
> Your app **may be removed** if you've stepped over the line and used content without permission.

这不是"审核可能被拒"，而是**上架后仍可被下架**。

---

## 二、苹果的原文（已核实）

### 4.2 最低功能性

> Your app should include features, content, and UI that **elevate it beyond a
> repackaged website**. If your app is not particularly useful, unique, or
> "app-like," it doesn't belong on the App Store.

### 4.2.2

> Other than catalogs, apps shouldn't primarily be marketing materials,
> advertisements, web clippings, **content aggregators**, or a collection of links.

→ 一个网球数据看板很可能被归类为 content aggregator。**必须靠原生功能跨过这条线**（见第五节）。

### 5.2 知识产权

> Make sure your app only includes content that you created or that you have a
> license to use. Your app may be removed if you've stepped over the line and used
> content without permission.

### 5.2.1

> Don't use protected third-party material such as **trademarks, copyrighted
> works**, or patented ideas in your app **without permission**, and don't include
> misleading, false, or copycat representations, names, or metadata.

→ 这条同时管两个东西：**数据**和**名字里的 ATP / WTA**。

### 5.1.1 隐私政策（必需）

> All apps must include a link to their privacy policy in the App Store Connect
> metadata field and within the app in an easily accessible manner.

---

## 三、你必须办理的事（我无法代劳）

### 1. 数据授权 —— 最关键

现状对照：

| 项目 | 数据来源 | 当前性质 | 头像 |
|---|---|---|---|
| WTA 站 | WTA 官方公开接口 | © WTA Tour, Inc.，非商业信息用途 | 热链 WTA 图片服务器 |
| ATP 站 | Tennis Explorer / Tennis Abstract | 转载，非商业信息用途 | 热链 tennisexplorer |

**两个 README 里写的「非商业信息目的」是网站场景下的合理使用，不能覆盖 App Store 分发。**
而且**热链图片在 app 里绝对不行**——app bundle 会被审查，且图片是明确的版权物。

可选路径（按现实可行度排序）：

| 路径 | 说明 | 你需要做的 |
|---|---|---|
| **A. 购买商业数据授权** | 这是唯一能让 app 长期稳定上架的路 | 向 **Sportradar / SportsDataIO / Enetpulse / TXOdds** 等网球数据商询价；也可直接联系 ATP/WTA 的商务部门 |
| **B. 自建数据** | 只收录你能合法获取的数据（例如你自己现场记录、或仅用 CC0 来源） | 接受数据覆盖面大幅缩水 |
| **C. 仅上架"工具"功能** | app 只提供赛程计算、比分记录、H2H 记录等**不含他人版权数据**的功能 | 重新定义产品 |
| **D. 换源** | 找有明确商用许可的数据源 | 逐家确认许可条款允许 App Store 分发 |

⚠️ 注意：Jeff Sackmann 的网球数据集已从 GitHub 下架；其原许可为 **CC-BY-NC-SA**（**禁止商业使用**），即使能拿到也不适用于 App Store。

**关于费用**：我没有从苹果或数据商的页面上直接读到具体报价，无法给你数字——数据授权动辄按年计费且需议价，请以询价结果为准。

### 2. 商标 —— 换名字

现在站名直接含 **ATP** / **WTA**，这是他人商标。5.2.1 明确禁止未经许可使用。

**必须换成本身不含商标的名字**，且描述里也只能做"事实性指称"（例如 "ATP 巡回赛数据" 作为描述性说明通常可以，但**不能作为 app 名称或图标主体**）。

候选名（都不含商标，供你选）：
- **Baseline** —— 球场基线，网球语汇，简短
- **Topspin**
- **Deuce**
- **Centre Court**
- **Tour Tennis**

我建议 **Baseline**，但它是否已被占用需要你在 App Store Connect 里查重。

### 3. Apple Developer Program

- 注册开发者账号（个人或公司主体）
- **年费金额我没能从苹果页面直接读到**（页面是 JS 渲染的），请以 developer.apple.com 实时报价为准
- 决定开发者主体用个人还是公司（涉及 5.2.1 里"由拥有权利的主体提交"的要求——**如果你拿到了数据授权，最好以持有授权的主体提交**）

### 4. App Store Connect 配置

- 创建 app 记录、填写元数据、上传构建
- 提供**隐私政策 URL**（我可以起草，见第四节）
- 提供**技术支持 URL**
- 填写 App Privacy 问卷（本 app 若只做本地收藏、不收集个人数据，问卷会很简单）

---

## 四、我可以直接做的事（不需要你等待授权）

| 项目 | 说明 | 状态 |
|---|---|---|
| **文档（本文）** | 上架路线图 | ✅ 已完成 |
| **隐私政策** | 5.1.1 必需，我能起草中英文版 | 待你确认后做 |
| **App Store 文案** | 名称、副标题、描述、关键词、更新说明 | 可做 |
| **截图** | 用 Playwright 按 App Store 要求的尺寸生成（6.7" 1290×2796 等） | 可做 |
| **App 图标** | 1024×1024，需自备（不能含 ATP/WTA 标志） | 可做 |
| **离线数据包** | 把站点裁剪成可打进 app 的体积 | 可做 |
| **iOS 工程源码** | SwiftUI + WKWebView + 原生功能 | 可写，但**本机无法构建**（见第七节） |
| **推送后端** | 比赛结果推送需要的小服务 | 可做（需你决定是否要推送） |

---

## 五、跨过 4.2 需要的原生功能

光套 WebView 大概率被拒。要做出"app-like"的实质功能，按性价比排序：

1. **完整离线** —— 站点数据已全部内联在 HTML 里，整包打进 app 即可断网使用（这是最强的差异化，也是技术上最容易的）
2. **收藏球员** —— 本地存储，无需账号
3. **比赛结果推送** —— 关注的球员有新赛果时通知（需要一个小后端）
4. **桌面小组件** —— WidgetKit 显示关注的球员排名／今日赛程
5. **Live Activity** —— 进行中的比赛实时比分（需要后端推送）
6. **分享** —— 原生分享面板分享球员／H2H

1 + 2 + 4 是投入最小、最容易被审核认可的组合。

---

## 六、建议的执行顺序

```
第 0 步  你：确认走"商业数据授权"路线并开始询价（周期最长，先启动）
         │
第 1 步  我：定名 + 隐私政策 + 文案 + 截图 + 图标（不依赖授权）
         │
第 2 步  你：注册 Apple Developer Program
         │
第 3 步  我：写 iOS 工程（离线打包 + 收藏 + 小组件）
         你：装 Xcode（约 40GB，本机磁盘够）
         │
第 4 步  我/你：真机联调、TestFlight 内测（此时授权应已有眉目）
         │
第 5 步  授权到位 → 提交审核
         授权未到位 → 停在 TestFlight，不要提交
```

**关键**：第 0 步和第 1–3 步可以并行。数据授权谈判周期通常以月计，所以**现在就启动询价**，其余工作我这边推进。

---

## 七、本机环境限制（重要）

我核实了当前开发机：

| 项目 | 状态 |
|---|---|
| Xcode | ❌ **未安装**（只有 Command Line Tools） |
| iOS SDK | ❌ 不存在（`xcrun --sdk iphoneos` 报错） |
| iOS 模拟器 | ❌ 不可用 |
| Swift | ✅ 6.4（仅能编译 macOS 目标） |
| 磁盘可用 | ✅ 198 GB（装 Xcode 绰绰有余） |

**含义**：我可以写出完整的 iOS 工程源码，但**无法在本机构建、运行或验证**它。
要进入第 3 步，你需要：

```bash
# 从 App Store 安装 Xcode（约 40GB），然后
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcodebuild -version          # 应输出版本号
xcrun --sdk iphoneos --show-sdk-path   # 应有路径
```

装好之后告诉我，我就能构建、跑模拟器、截图并验证。

---

## 八、当前状态

- [x] 路线确认：正式上架 App Store
- [x] 条款核实：4.2 / 4.2.2 / 5.1.1 / 5.2 / 5.2.1 原文已引
- [x] 环境核实：本机无 Xcode / iOS SDK
- [ ] 数据授权（你）
- [ ] 定名
- [ ] Apple Developer Program（你）
- [ ] 隐私政策 / 文案 / 截图 / 图标
- [ ] iOS 工程
- [ ] TestFlight 内测
- [ ] 提交审核
