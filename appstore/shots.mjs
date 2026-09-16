/**
 * App Store screenshot generator.
 *
 * Captures the key screens at an App Store-accepted size and overlays a caption
 * bar.  Viewport 430×932 at deviceScaleFactor 3 renders exactly 1290×2796 — the
 * iPhone 6.7" size.
 *
 *   node appstore/shots.mjs http://127.0.0.1:4175/ ../screenshots
 *
 * These are drafts captured from the web build; re-run against the real app
 * before submitting (point BASE at the app's URL scheme or a local copy).
 */
import { chromium } from '/opt/homebrew/lib/node_modules/playwright/index.mjs';

const BASE = process.argv[2] || 'http://127.0.0.1:4175/';
const OUT = process.argv[3] || new URL('./screenshots/', import.meta.url).pathname;

const SHOTS = [
  ['index', '赛季总览 · 冠军与最新赛果', 'Season overview'],
  ['rankings', '官方单打世界排名', 'Official singles ranking'],
  ['player-sinner-8b8e8', '球员档案 · 战绩与场地胜率', 'Player profile'],
  ['calendar', '整个赛季的赛程', 'The season calendar'],
  ['h2h-alcaraz-5ab70-sinner-8b8e8', '交手记录与数据对比', 'Head-to-head'],
  ['event-wimbledon-2026', '完整单打签表', 'Complete draw'],
];

const b = await chromium.launch();
const ctx = await b.newContext({
  viewport: { width: 430, height: 932 },
  deviceScaleFactor: 3,
  javaScriptEnabled: false,
  locale: 'zh-CN',
});
const page = await ctx.newPage();

for (const [slug, zh, en] of SHOTS) {
  await page.goto(BASE + slug + '.html', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(1800);
  // 顶部品牌条 + 底部说明条，模拟 App Store 展示样式
  await page.evaluate(({ zh, en }) => {
    const bar = document.createElement('div');
    bar.style.cssText = `position:fixed;left:0;right:0;bottom:0;z-index:9999;
      padding:22px 22px 30px;background:linear-gradient(0deg,rgba(6,20,14,.97),rgba(6,20,14,.82) 60%,transparent);
      font-family:-apple-system,"PingFang SC",sans-serif;color:#e9f2ea;pointer-events:none`;
    bar.innerHTML = `<div style="font-size:26px;font-weight:800;letter-spacing:-.01em">${zh}</div>
      <div style="font-size:14px;opacity:.62;margin-top:5px;letter-spacing:.06em;text-transform:uppercase">${en}</div>`;
    document.body.appendChild(bar);
  }, { zh, en });
  await page.screenshot({ path: `${OUT}/${slug}.png` });
  console.log(`  ✓ ${slug}.png`);
}
await b.close();
