// Run from a film's folder (make.sh does): renders its index.html (lib/film.js + the film's render.js) with playwright.
// node ../../lib/capture.mjs stills 1.5,10,20     -> build/still_<t>.png
// node ../../lib/capture.mjs audit 1.5,10,20 36   -> small text, text over text, text under the platform's buttons
// node ../../lib/capture.mjs dense [0.5] [36]     -> those three only, on a frame every 0.5 s all through the film, each finding
//                                                     given as the stretches it lasts: an overlap inside a transition falls between
//                                                     the frames check samples (运动, 2026-10-18: four more turned up this way)
// node ../../lib/capture.mjs crash                -> renders the frames most likely to throw, without saving them: every frame of
//                                                     every transition (a scene fading in is drawn at a negative local time), the
//                                                     first frames of every scene, every line and the film, one frame a second, the last frames
// node ../../lib/capture.mjs endline '完整版 · 在视频号' out.png   -> the teaser's last line, in the film's type (lib/teaser.py)
// node ../../lib/capture.mjs render [workers]      -> build/seg_<k>.mp4 (10 s each) + build/segs.txt + build/segs.json (END=<s>: only the start)
// node ../../lib/capture.mjs render [workers] 95.5-101,300
//                                                  -> only the segments holding those times again (a time, or a span from-to, in
//                                                     seconds), then segs.txt as before: a fix in one scene costs a minute, not the film
import { createRequire } from 'module';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright-core');

const ROOT = process.cwd();   // the film's folder
const BUILD = path.join(ROOT, 'build');
const TL = JSON.parse(fs.readFileSync(path.join(ROOT, 'timeline.json'), 'utf8'));
const FILM = fs.existsSync(path.join(ROOT, '片子.json')) ? JSON.parse(fs.readFileSync(path.join(ROOT, '片子.json'), 'utf8')) : {};   // new.sh's
const FPS = 30;
const url = pathToFileURL(path.join(ROOT, 'index.html')).href;

async function openPage(browser) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.error('PAGE ERROR', e.message));
  await page.goto(url);
  await page.evaluate(() => window.ready);
  return page;
}

async function stills(times) {
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const page = await openPage(browser);
  for (const t of times) {
    await page.evaluate(t => window.renderFrame(t), t);
    await shot(page, { path: path.join(BUILD, `still_${t}.png`) });
  }
  await browser.close();
}

// a screenshot now and then times out (掏钱, 2026-10-08/09: once in the qc sheets, once 85% into a render, which cannot resume):
// wait longer and try again before giving up
async function shot(page, opts) {
  for (let k = 0; ; k++) {
    try { return await page.screenshot({ timeout: 60000, ...opts }); }
    catch (e) { if (k >= 2 || e.name !== 'TimeoutError') throw e; console.log(`截图超时，第 ${k + 1} 次重试`); await page.waitForTimeout(2000); }
  }
}

// the teaser's last line (lib/teaser.py), drawn by the film's own page so it has the film's type and colours: in the
// subtitle's place (the teaser ends on a held frame with no subtitle), on a soft dark band, on a transparent 1080×1920 PNG
async function endLine(text, out) {
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const page = await openPage(browser);
  const url = await page.evaluate(s => {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const keep = ctx; ctx = c.getContext('2d');
    try {
      const sc = K.subShade || '6,8,14', band = ctx.createLinearGradient(0, SUB_Y - 110, 0, SUB_Y + 110);
      band.addColorStop(0, `rgba(${sc},0)`); band.addColorStop(.5, `rgba(${sc},.6)`); band.addColorStop(1, `rgba(${sc},0)`);
      ctx.fillStyle = band; ctx.fillRect(0, SUB_Y - 110, W, 220);
      txt(s, CX, SUB_Y, { font: `600 56px ${FT.ui}`, color: K.subInk || '#FFFFFF', ls: 4 });
    } finally { ctx = keep; }
    return c.toDataURL('image/png');
  }, text);
  fs.writeFileSync(out, Buffer.from(url.split(',')[1], 'base64'));
  await browser.close();
}

// the film is rendered in segments of CHUNK frames, handed out to the workers one at a time; build/segs.json keeps the plan,
// so a later render can redo only the segments a fix touched (大理: the first full render ran 20 minutes and died on one frame)
const CHUNK = Math.round(Number(process.env.CHUNK || 10) * FPS);
async function renderSegs(N, total, ks) {
  const queue = [...ks];
  const one = async (w) => {
    const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
    const page = await openPage(browser);
    for (let k = queue.shift(); k !== undefined; k = queue.shift()) {
      const f0 = k * CHUNK, f1 = Math.min(total, (k + 1) * CHUNK), out = path.join(BUILD, `seg_${k}.mp4`);
      const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
        ...(process.env.VENC === 'videotoolbox' ? ['-c:v', 'h264_videotoolbox', '-b:v', '12M'] : ['-c:v', 'libx264', '-preset', 'medium', '-crf', '17']), '-pix_fmt', 'yuv420p', '-r', String(FPS), out]);
      for (let f = f0; f < f1; f++) {
        await page.evaluate(t => window.renderFrame(t), f / FPS);
        const buf = await shot(page, { type: 'jpeg', quality: 94 });
        if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      }
      ff.stdin.end();
      await new Promise(r => ff.on('close', r));
      console.log(`w${w} seg_${k}  ${(f0 / FPS).toFixed(1)}–${(f1 / FPS).toFixed(1)}s  （还剩 ${queue.length} 段）`);
    }
    await browser.close();
  };
  await Promise.all([...Array(Math.min(N, ks.length))].map((_, w) => one(w)));
}

// the frames most likely to throw: a scene fading in is drawn before its own start (a negative local time), where a cycle
// written t % 1 goes negative (use frac()); and the first and last frames. Nothing is saved; every frame that throws is listed.
async function crashScan() {
  const S = TL.scenes, total = Math.ceil(TL.duration * FPS), fs_ = new Set();
  const add = (f0, f1) => { for (let f = Math.max(0, f0); f < Math.min(total, f1); f++) fs_.add(f); };
  add(0, 6); add(total - 3, total);
  for (let f = 0; f < total; f += FPS) add(f, f + 1);                       // one frame a second all through
  for (const s of S) {
    add(Math.floor(s.start * FPS), Math.floor(s.start * FPS) + 6);
    if (s.out !== undefined && s.trans) add(Math.floor(s.out * FPS), Math.ceil((s.out + TL.trans[s.trans]) * FPS) + 1);
    for (const c of s.cues) add(Math.floor((s.start + c.start) * FPS) - 1, Math.floor((s.start + c.start) * FPS) + 3);   // where each line's things come in
  }
  const frames = [...fs_].sort((a, b) => a - b);
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const page = await openPage(browser);
  const bad = await page.evaluate(([frames, FPS]) => {
    const out = [];
    for (const f of frames) {
      try { window.renderFrame(f / FPS); }
      catch (e) { out.push([f, String(e && e.message || e), String(e && e.stack || '').split('\n').slice(1, 3).map(s => s.trim()).join(' ← ')]); }
    }
    return out;
  }, [frames, FPS]);
  await browser.close();
  const where = t => { const s = [...S].reverse().find(s => t >= s.start) || S[0]; return `${s.id} 场内 ${(t - s.start).toFixed(2)}s`; };
  console.log(`崩溃扫描：渲染了 ${frames.length} 帧（每个转场的每一帧、每场和全片开头 6 帧、每句开头几帧、每秒一帧、结尾 3 帧）。${bad.length ? `${bad.length} 帧会崩：` : '没有会崩的帧'}`);
  const groups = new Map();            // one line per place in the code (the message carries the value, which differs per frame)
  for (const [f, msg, at] of bad) {
    const k = at || msg.replace(/-?\d+(\.\d+)?/g, '#');
    if (!groups.has(k)) groups.set(k, { msg, at, fs: [] });
    groups.get(k).fs.push(f);
  }
  const short = s => { try { s = decodeURIComponent(s); } catch (e) { } return s.split('file://' + ROOT + '/').join('').split('file://' + path.dirname(path.dirname(ROOT)) + '/').join(''); };
  for (const { msg, at: at0, fs } of groups.values()) {
    const at = short(at0);
    const t0 = fs[0] / FPS, t1 = fs[fs.length - 1] / FPS;
    console.log(`  ${t0.toFixed(2)}s（${where(t0)}）起，${fs.length} 帧${fs.length > 1 ? `，到 ${t1.toFixed(2)}s` : ''}：${msg}${at ? `\n      ${at}` : ''}`);
  }
  // a hint, not a stop: x % 1 in the film's own code goes negative for a negative x
  const hints = [];
  for (const f of fs.readdirSync(ROOT).filter(f => f.endsWith('.js') && f !== 'timeline.js')) {
    fs.readFileSync(path.join(ROOT, f), 'utf8').split('\n').forEach((l, i) => { if (/%\s*1(?![0-9.])/.test(l.replace(/\/\/.*$/, ''))) hints.push(`${f}:${i + 1}`); });
  }
  if (hints.length) console.log(`提示（不挡）：${hints.length} 处用了 % 1，场景淡入时时间是负的，取模也是负的；换成 frac()（lib/film.js）：${hints.slice(0, 12).join('，')}${hints.length > 12 ? ' …' : ''}`);
  if (bad.length) process.exit(1);
}

async function auditText(times, limit, step = 0) {
  // text smaller than `limit` px on the 1080-wide frame is hard to read on a phone;
  // two clearly visible pieces of text whose boxes overlap are drawn over each other.
  // step: the dense pass (frames that far apart): every time a text finding is seen is kept, and only the text is reported
  const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const page = await openPage(browser);
  const small = new Map(), over = new Map(), zone = new Map(), onPeople = new Map(), cut = new Map(), inCol = new Map();
  const keep = step ? Infinity : 4;   // how many times a text finding lists
  // where the platform draws over the video on a phone (1080×1920): status bar, the like/comment column, the caption block.
  // One set per platform; a film checks against every platform in its 片子.json (Douyin when there is none). 视频号's own
  // layout has not been measured yet: until a screenshot is, it is checked like Douyin's (规格/平台.md)
  const ZONES = {
    抖音: [[0, 0, 1080, 120, '顶部状态栏'], [960, 760, 1080, 1560, '右侧点赞评论栏'], [0, 1640, 1080, 1920, '底部文案区']],
    视频号: [[0, 0, 1080, 120, '顶部状态栏'], [960, 760, 1080, 1560, '右侧点赞评论栏'], [0, 1640, 1080, 1920, '底部文案区']],
  };
  const plats = (FILM.平台 || ['抖音']).filter(p => ZONES[p]);
  const UNSAFE = [...new Map((plats.length ? plats : ['抖音']).flatMap(p => ZONES[p]).map(z => [z.join(), z])).values()];
  const area = r => Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]);
  for (const t of times) {
    const found = await page.evaluate(t => { window.AUDIT = []; window.renderFrame(t); const a = window.AUDIT; window.AUDIT = null; return a; }, t);
    const ent = found.map(([s, px, a, b, sc], i) => ({ i, s, px, a, b, sc: sc ?? -1 }));
    const covers = ent.filter(e => e.s === '#cover');
    for (const c of ent.filter(e => e.s === '#chip' && e.a >= .35)) for (const e of ent) {   // scene text running under the corner chapter tag
      if (!e.b || e.s.startsWith('#') || e.i > c.i || e.sc < 0 || e.a < .35) continue;
      const R = [Math.max(e.b[0], c.b[0] - 8), Math.max(e.b[1], c.b[1] - 8), Math.min(e.b[2], c.b[2] + 8), Math.min(e.b[3], c.b[3] + 8)];
      if (area(R) < .05 * area(e.b)) continue;
      const k = `${e.s.slice(0, 16)}  ×  〔章节标签〕`; const v = over.get(k) || []; if (v.length < keep) v.push(t); over.set(k, v);
    }
    // how visible a piece of text still is at (x, y) after the covers drawn over it
    const vis = (e, x, y) => covers.reduce((v, c) => c.i > e.i && x >= c.b[0] && x <= c.b[2] && y >= c.b[1] && y <= c.b[3] ? v * (1 - c.a) : v, e.a);
    const texts = ent.filter(e => !e.s.startsWith('#'));
    const seen = e => !e.b || vis(e, (e.b[0] + e.b[2]) / 2, (e.b[1] + e.b[3]) / 2) >= .35;
    for (const { s, px } of texts.filter(seen)) if (px < limit) { const k = s.slice(0, 24); const v = small.get(k) || { px, times: [] }; v.px = Math.min(v.px, px); if (v.times.length < keep) v.times.push(t); small.set(k, v); }
    for (const e of texts.filter(seen)) {
      if (!e.b) continue;
      for (const [x0, y0, x1, y1, name] of UNSAFE) {
        const R = [Math.max(e.b[0], x0), Math.max(e.b[1], y0), Math.min(e.b[2], x1), Math.min(e.b[3], y1)];
        if (area(R) <= .03 * area(e.b)) continue;
        const k = `${e.s.slice(0, 16)}  ×  〔${name}〕`; const v = zone.get(k) || []; if (v.length < keep) v.push(t); zone.set(k, v);
      }
    }
    // people: a subtitle running over someone on screen; someone standing half out of the frame (等于没说)
    for (const p of ent.filter(e => e.s.startsWith('#subject:') && e.b && e.b[3] - e.b[1] >= 120)) {
      if (vis(p, (p.b[0] + p.b[2]) / 2, (p.b[1] + p.b[3]) / 2) < .35) continue;
      const who = p.s.slice(9);
      // the box ends at the soles' line; shoes hang a little below it, so the feet count too (掏钱: subtitles on her feet, 6% never reached)
      const pb = [p.b[0], p.b[1], p.b[2], p.b[3] + .04 * (p.b[3] - p.b[1])];
      for (const sb of texts.filter(e => e.b && e.s.startsWith('〔字幕〕') && e.i > p.i && seen(e))) {
        const R = [Math.max(pb[0], sb.b[0]), Math.max(pb[1], sb.b[1]), Math.min(pb[2], sb.b[2]), Math.min(pb[3], sb.b[3])];
        if (area(R) < .06 * area(p.b) && !(R[3] - R[1] >= 6 && R[2] - R[0] >= 40)) continue;
        const k = `${sb.s.slice(4, 18)}  ×  〔${who}〕`; const v = onPeople.get(k) || []; if (v.length < 4) v.push(t); onPeople.set(k, v);
      }
      const F = [Math.max(p.b[0], 0), Math.max(p.b[1], 0), Math.min(p.b[2], 1080), Math.min(p.b[3], 1920)], inside = area(F) / Math.max(1, area(p.b));
      if (inside > .15 && inside < .85) { const k = `〔${who}〕 露出 ${Math.round(inside * 100)}%`; const v = cut.get(who) || []; if (v.length < 6) v.push(t); cut.set(who, v); }
      // someone standing in the like/comment column: the icons sit on them (掏钱: the old man at the right end of the row)
      const C = [Math.max(F[0], 960), Math.max(F[1], 760), Math.min(F[2], 1080), Math.min(F[3], 1560)];
      if (area(F) > 0 && area(C) / area(F) > .12) { const v = inCol.get(who) || []; if (v.length < 6) v.push(t); inCol.set(who, v); }
    }
    const boxed = texts.filter(e => e.b && e.px >= 16);
    for (let i = 0; i < boxed.length; i++) for (let j = i + 1; j < boxed.length; j++) {
      const p = boxed[i], q = boxed[j];
      if (p.sc >= 0 && q.sc >= 0 && p.sc !== q.sc) continue;            // two scenes cross-fading
      const R = [Math.max(p.b[0], q.b[0]), Math.max(p.b[1], q.b[1]), Math.min(p.b[2], q.b[2]), Math.min(p.b[3], q.b[3])];
      if (area(R) < .15 * Math.min(area(p.b), area(q.b))) continue;     // a corner brushing past is not an overlap
      const x = (R[0] + R[2]) / 2, y = (R[1] + R[3]) / 2;
      if (vis(p, x, y) < .25 || vis(q, x, y) < .25) continue;          // one of them is covered or dimmed out of sight there
      const k = [p.s.slice(0, 16), q.s.slice(0, 16)].sort().join('  ×  ');
      const v = over.get(k) || []; if (v.length < keep) v.push(t); over.set(k, v);
    }
  }
  await browser.close();
  const rows = [...small.entries()].sort((a, b) => a[1].px - b[1].px);
  if (step) {
    // the times a finding was seen, run together where one frame follows the next: '145.5–146.5, 300'
    const spans = ts => {
      const out = [];
      for (const t of ts) { const s = out[out.length - 1]; if (s && t - s[1] <= step * 1.5) s[1] = t; else out.push([t, t]); }
      return out.map(([a, b]) => a === b ? `${a}` : `${a}–${b}`).join(', ');
    };
    console.log(`全片密查字：每 ${step} 秒一帧，${times.length} 帧（只查字：界面区、小字、字压字；人和别的看 check）`);
    console.log(`压在平台界面区的字（手机上会被状态栏、点赞评论栏、底部文案挡住）：${zone.size} 处`);
    for (const [k, v] of zone) console.log(`  ${k}  @ ${spans(v)}`);
    console.log(`小于 ${limit}px 的字（1080 宽画面上，手机上会难认）：${rows.length} 处`);
    for (const [s, v] of rows) console.log(`${String(v.px).padStart(3)}px  ${s}  @ ${spans(v.times)}`);
    console.log(`字压着字（两段都清楚可见、字框重叠）：${over.size} 处`);
    for (const [k, v] of over) console.log(`  ${k}  @ ${spans(v)}`);
    return;
  }
  console.log(`压在平台界面区的字（手机上会被状态栏、点赞评论栏、底部文案挡住）：${zone.size} 处`);
  for (const [k, v] of zone) console.log(`  ${k}  @ ${v.join(', ')}`);
  console.log(`小于 ${limit}px 的字（1080 宽画面上，手机上会难认）：${rows.length} 处`);
  for (const [s, v] of rows) console.log(`${String(v.px).padStart(3)}px  ${s}  @ ${v.times.join(', ')}`);
  console.log(`字压着字（两段都清楚可见、字框重叠）：${over.size} 处`);
  for (const [k, v] of over) console.log(`  ${k}  @ ${v.join(', ')}`);
  console.log(`字幕压着人（字幕横在画面里的人身上，前景的人要站在字幕上方）：${onPeople.size} 处`);
  for (const [k, v] of onPeople) console.log(`  ${k}  @ ${v.join(', ')}`);
  console.log(`人被画面边缘切掉（只露出 15%–85%，走进走出的那一下可以不管）：${[...cut.values()].reduce((n, v) => n + v.length, 0)} 处`);
  for (const [k, v] of cut) console.log(`  〔${k}〕  @ ${v.join(', ')}`);
  console.log(`人站进右侧点赞评论栏（x 960 以右、y 760–1560 占了这个人 12% 以上，走进走出的那一下可以不管）：${[...inCol.values()].reduce((n, v) => n + v.length, 0)} 处`);
  for (const [k, v] of inCol) console.log(`  〔${k}〕  @ ${v.join(', ')}`);
}

const [mode, arg] = process.argv.slice(2);
if (mode === 'stills') await stills(arg.split(',').map(Number));
else if (mode === 'audit') await auditText(arg.split(',').map(Number), Number(process.argv[4] || 30));
else if (mode === 'dense') {
  const step = Number(arg || .5), T = [];
  for (let k = 0; k * step < TL.duration; k++) T.push(Math.round(k * step * 1000) / 1000);
  await auditText(T, Number(process.argv[4] || 36), step);
}
else if (mode === 'crash') await crashScan();
else if (mode === 'endline') await endLine(arg, process.argv[4]);
else {
  const N = Number(arg || 5), only = process.argv[4];
  const total = Math.ceil(Math.min(TL.duration, Number(process.env.END || TL.duration)) * FPS);   // END=<seconds>: render only the start (a preview)
  const nseg = Math.ceil(total / CHUNK), plan = path.join(BUILD, 'segs.json');
  let ks = [...Array(nseg).keys()];
  if (only) {
    const old = fs.existsSync(plan) ? JSON.parse(fs.readFileSync(plan, 'utf8')) : null;
    if (!old || old.total !== total || old.chunk !== CHUNK) {
      console.error(old ? `时间轴变了，或者 END、分段长度和上次不一样（${old.total} 帧 → ${total} 帧）：只能全片重渲（./make.sh render）。`
        : '还没有按段渲染过（build/segs.json 不在）：先全片渲染一遍（./make.sh render）。');
      process.exit(1);
    }
    const want = new Set();
    for (const part of only.split(',')) {
      const [a, b] = part.split('-').map(Number), lo = Math.max(0, Math.floor(a * FPS / CHUNK)), hi = Math.min(nseg - 1, Math.floor((isNaN(b) ? a : b) * FPS / CHUNK));
      for (let k = lo; k <= hi; k++) want.add(k);
    }
    const missing = ks.filter(k => !want.has(k) && !fs.existsSync(path.join(BUILD, `seg_${k}.mp4`)));
    if (missing.length) { console.error(`有 ${missing.length} 段不在 build/ 里（比如 seg_${missing[0]}.mp4）：先全片渲染一遍。`); process.exit(1); }
    ks = [...want].sort((a, b) => a - b);
    console.log(`只重渲 ${ks.length} 段：${ks.map(k => `${(k * CHUNK / FPS).toFixed(0)}–${(Math.min(total, (k + 1) * CHUNK) / FPS).toFixed(0)}s`).join('，')}`);
  }
  await renderSegs(N, total, ks);
  fs.writeFileSync(path.join(BUILD, 'segs.txt'), [...Array(nseg).keys()].map(k => `file '${path.join(BUILD, `seg_${k}.mp4`)}'`).join('\n'));
  fs.writeFileSync(plan, JSON.stringify({ fps: FPS, total, chunk: CHUNK, segs: nseg }));
  for (const f of fs.readdirSync(BUILD)) {   // segments left over from a longer render, or the old one-per-worker ones
    const m = /^seg_(\d+)\.mp4$/.exec(f); if (m && Number(m[1]) >= nseg) fs.unlinkSync(path.join(BUILD, f));
  }
  console.log('frames', total, only ? `（重渲 ${ks.length} 段，其余沿用）` : `（${nseg} 段）`);
}
