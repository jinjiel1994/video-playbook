// Checks over time, the kind a single still cannot show. Run from a film's folder (make.sh check / qc do):
//   node ../../lib/timecheck.mjs        (STILL=<seconds> sets how long the picture may stay unchanged, default 6)
// 1. every chapter name in its transition: how long it is readable (at least 50% visible). The rule is 1.5 s.
// 2. transitions: a scene's text showing through while the chapter name is up.
// 3. the picture not changing for STILL seconds while the voice goes on (subtitles and grain do not count as change).
// 4. text on screen gone before it can be read: 0.4 s + 1 s for every 7 characters (a Latin word counts as one), at least
//    1 s. Left out: words being spoken at the time (big lines instead of subtitles), text being typed in or deleted, the end card.
// It reads the same audit the film's txt()/reveal() write (lib/film.js), so it works for every film built on it.
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright-core');

const ROOT = process.cwd();
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const S = TL.scenes;
const STILL = Number(process.env.STILL || 6), STEP = 0.4, TFPS = 15;

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
page.on('pageerror', e => console.error('PAGE ERROR', e.message));
await page.goto(pathToFileURL(path.join(ROOT, 'index.html')).href);
await page.evaluate(() => window.ready);
await page.evaluate(() => {
  // grain is noise that changes every frame: hold it still so only the picture counts as change
  if (typeof GRAIN !== 'undefined' && GRAIN.length) GRAIN = GRAIN.map(() => GRAIN[0]);
  const c = document.createElement('canvas'); c.width = 108; c.height = 192;
  window.__tc = { x: c.getContext('2d', { willReadFrequently: true }), anchor: null };
});

// one frame: the audit entries, and (with diff) the share of the picture that changed since the last change
const frame = (t, diff) => page.evaluate(([t, diff]) => {
  window.AUDIT = []; window.renderFrame(t); const a = window.AUDIT; window.AUDIT = null;
  if (!diff) return [a, null];
  const { x } = window.__tc; x.drawImage(cv, 0, 0, 108, 192);
  const d = x.getImageData(0, 0, 108, 192).data, y0 = Math.floor((SUB_Y - 100) / 10), y1 = Math.ceil((SUB_Y + 100) / 10);
  const p = window.__tc.anchor; if (!p) { window.__tc.anchor = d; return [a, 1]; }
  let n = 0, k = 0;
  for (let y = 0; y < 192; y++) {
    if (y >= y0 && y <= y1) continue;                    // the subtitle band
    for (let i = y * 432; i < y * 432 + 432; i += 4) {
      n++;
      if (Math.abs(d[i] - p[i]) + Math.abs(d[i + 1] - p[i + 1]) + Math.abs(d[i + 2] - p[i + 2]) > 24) k++;
    }
  }
  const ch = k / n; if (ch > .002) window.__tc.anchor = d;   // 0.2% of the picture: about one small label
  return [a, ch];
}, [t, diff]);

// how visible each piece of text is after whatever is drawn over it (the same rule as capture.mjs audit)
function entries(found) {
  const ent = found.map(([s, px, a, b, sc], i) => ({ i, s, px, a, b, sc: sc ?? -1 }));
  const covers = ent.filter(e => e.s === '#cover');
  const vis = e => {
    if (!e.b) return e.a;
    const x = (e.b[0] + e.b[2]) / 2, y = (e.b[1] + e.b[3]) / 2;
    return covers.reduce((v, c) => c.i > e.i && x >= c.b[0] && x <= c.b[2] && y >= c.b[1] && y <= c.b[3] ? v * (1 - c.a) : v, e.a);
  };
  return ent.filter(e => !e.s.startsWith('#')).map(e => ({ ...e, v: vis(e) }));
}
const sub = e => e.s.startsWith('〔字幕〕');
const fmt = t => t.toFixed(1);

// ---- 1 and 2: the transitions ----
const chapters = [], bleed = new Map();
for (let k = 0; k < S.length - 1; k++) {
  const s = S[k], nx = S[k + 1];
  if (s.out == null || !nx.name) continue;
  const D = TL.trans[s.trans]; let readable = 0, full = 0;
  for (let f = 0; f <= Math.round(D * TFPS); f++) {
    const t = s.out + f / TFPS, ent = entries((await frame(t, false))[0]);
    const name = Math.max(0, ...ent.filter(e => e.s === nx.name).map(e => e.v));
    if (name >= .5) readable++;
    if (name >= .9) full++;
    if (name >= .35) for (const e of ent) {
      if (sub(e) || (e.sc !== k && e.sc !== k + 1) || e.v < .25) continue;
      const key = `${nx.name} ← 「${e.s.slice(0, 16)}」`; if (!bleed.has(key)) bleed.set(key, t);
    }
  }
  chapters.push({ name: nx.name, at: s.out, type: s.trans, readable: readable / TFPS, full: full / TFPS });
}

// ---- 3 and 4: the whole film, one frame every STEP seconds ----
const changes = [], present = new Map(), shown = [];
const last = S[S.length - 1], endCard = last.endHold != null ? last.start + last.endHold : TL.duration;
const n = Math.floor(TL.duration / STEP);
for (let i = 0; i <= n; i++) {
  const t = i * STEP, [found, ch] = await frame(t, true);
  if (ch > .002) changes.push(t);
  const now = new Set(entries(found).filter(e => !sub(e) && e.v >= .5 && e.sc < 100).map(e => e.s));
  shown.push(now);
  for (const s of now) { if (!present.has(s)) present.set(s, []); present.get(s).push(i); }
}
await browser.close();

const speech = S.flatMap(s => s.cues.map(c => [s.start + c.start, s.start + c.end, s.id, c.text]));
const talk = (a, b) => speech.reduce((v, [x, y]) => v + Math.max(0, Math.min(b, y) - Math.max(a, x)), 0);
const stills = [];
for (let j = 0; j < changes.length; j++) {
  const a = changes[j], b = Math.min(j + 1 < changes.length ? changes[j + 1] : TL.duration, endCard);
  if (b - a >= STILL && talk(a, b) >= .5 * (b - a)) {
    const said = speech.filter(([x, y]) => y > a && x < b);
    stills.push({ a, b, id: said[0]?.[2] ?? '', said: said.map(z => z[3]).join(' ') });
  }
}

const short = [], bare = x => x.replace(/[\s，。：；？！、“”…—,.?!:;"'「」]/g, '');
const spoken = (s, a, b) => speech.some(([x, y, , text]) => y > a - 1 && x < b + 1 && bare(text).includes(bare(s)));
for (const [s, idx] of present) {
  const units = (s.match(/[A-Za-z]+|\d+|[^\sA-Za-z\d，。：；？！、“”…—,.?!:;"'「」]/g) || []).length;   // a CJK character or a Latin word
  if (units < 2 || /^[\d\s.,:：%¥$+\-−×/·]+$/.test(s)) continue;          // single marks, counters
  const need = Math.max(1, .4 + units / 7);
  for (let r = 0; r < idx.length;) {
    let q = r; while (q + 1 < idx.length && idx[q + 1] === idx[q] + 1) q++;
    const end = idx[q], next = shown[end + 1] ? [...shown[end + 1]] : [];
    const typing = next.some(x => x !== s && (x.startsWith(s) || s.startsWith(x)));   // still being typed in or deleted, letter by letter
    const dur = (q - r + 1) * STEP;
    const at = idx[r] * STEP;
    if (!typing && end < n && at < endCard && dur + STEP < need && !spoken(s, at, at + dur)) short.push({ s, at, dur, need, gap: need - dur });
    r = q + 1;
  }
}
short.sort((a, b) => b.gap - a.gap);

console.log('时间上的检查（单张静帧看不出来的）');
const badCh = chapters.filter(c => c.readable < 1.5);
console.log(`章节名停留（规矩：至少 1.5 秒；按 50% 以上可见算，括号里是全亮的时间）：${badCh.length ? `${badCh.length} 处不够` : '都够'}`);
for (const c of chapters) console.log(`  ${c.readable < 1.5 ? '不够 ' : ''}${c.name}  ${c.readable.toFixed(2)} 秒（全亮 ${c.full.toFixed(2)} 秒）  ${c.type} 转场 @ ${fmt(c.at)}s`);
const missing = S.slice(1).filter((s, k) => s.name && !chapters.some(c => c.name === s.name));
for (const s of missing) console.log(`  没在转场里找到章节名「${s.name}」：前一场不是转场接过来的，或者章节名不是用 txt() 画的，要看片确认`);
for (const c of chapters.filter(c => c.readable === 0)) console.log(`  「${c.name}」在转场里一直没出现：可能不是用 txt() 画的，要看片确认`);
console.log(`转场里透出场景的字（章节名亮着的时候，上一场或下一场的字还看得见）：${bleed.size} 处`);
for (const [k, t] of bleed) console.log(`  ${k}  @ ${fmt(t)}s`);
console.log(`画面超过 ${STILL} 秒没变化、旁白还在讲（字幕和颗粒不算变化，片尾卡不算）：${stills.length} 处`);
for (const x of stills) console.log(`  ${x.id}  ${fmt(x.a)}–${fmt(x.b)}s（${(x.b - x.a).toFixed(1)} 秒）  在念：${x.said.slice(0, 60)}`);
console.log(`字没停够读完（0.4 秒加每 7 个字 1 秒，至少 1 秒；正在念的字、打字删字的中途和片尾卡不算；每 ${STEP} 秒取一帧，差一帧以内不报）：${short.length} 处`);
for (const x of short.slice(0, 20)) console.log(`  「${x.s.slice(0, 24)}」 停约 ${x.dur.toFixed(1)} 秒，要 ${x.need.toFixed(1)} 秒  @ ${fmt(x.at)}s`);
