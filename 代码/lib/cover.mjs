// Run from a film's folder: node ../../lib/cover.mjs → build/cover_1.png … (one per design in the film's cover.js)
import { createRequire } from 'module'; import path from 'path'; import { pathToFileURL } from 'url';
const require = createRequire(import.meta.url); const { chromium } = require('playwright-core');
const ROOT = process.cwd();   // the film's folder
const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {}); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
p.on('pageerror', e => console.error('PAGE ERROR', e.message));
await p.goto(pathToFileURL(path.join(ROOT, 'cover.html')).href); await p.evaluate(() => window.ready);
await p.evaluate(() => document.fonts.load("900 100px \"Source Han Sans CN\"", window.COVER_TEXT || "追本"));
const n = await p.evaluate(() => COVERS.length);
for (let i = 0; i < n; i++) { await p.evaluate(i => window.renderCover(i), i); await p.screenshot({ path: path.join(ROOT, 'build', `cover_${i + 1}.png`) }); }
await b.close(); console.log(n, 'covers');
