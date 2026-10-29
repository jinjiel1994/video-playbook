// 把这里的几张 HTML 截成 ../*.png（1600×900）。在仓库根目录跑：node docs/img/src/render.mjs
// 浏览器：CHROME 环境变量指一个 chrome-headless-shell；不设就用 Playwright 自己的 chromium。字体要装 Noto Sans CJK SC。
import { chromium } from '../../../代码/node_modules/playwright-core/index.mjs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
const names = process.argv.slice(2).length ? process.argv.slice(2) : ['hero', 'pipeline', 'workflow', 'review', 'forms'];
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
for (const n of names) {
  await page.goto('file://' + path.join(here, n + '.html'));
  await page.evaluate(() => document.fonts.ready);
  const over = await page.evaluate(() => document.documentElement.scrollWidth > 1600 || document.documentElement.scrollHeight > 900);
  await page.screenshot({ path: path.join(here, '..', n + '.png') });
  console.log(n + '.png' + (over ? '  （内容超出画面，改一下）' : ''));
}
await browser.close();
