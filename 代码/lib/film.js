// The shared base of every film's picture. index.html loads it before the film's render.js; both run in the same
// global scope and the film's file comes second, so a film can declare any of these functions again to replace it.
// Here: the frame (W, H, SUB_Y, ctx), the timeline (TL, S; Q(sc).w(k, '字') = the moment those words are spoken),
// easing, txt()/reveal() with the legibility audit capture.mjs reads, panels, pills, the research/reading markers,
// a person at real proportions, big spoken lines, the question at the top, the chapter tag, subtitles, grain,
// renderFrame(t) and window.ready.
// The film's render.js defines K (its palette) and SCENE_FN {scene id: fn(lt, sc)}; optionally HL/HLC (a highlighted
// subtitle word takes the colour of what it means), TRANSITIONS {type: fn(k, t, p)} for its chapter transitions
// ('dissolve' is built in) and finishDim(t) (how much of the vignette to keep, e.g. less over a bright end card).
// K keys read here, with defaults: ink, dim, edge, panel, lav, bg0, pillFill, tagResearch, tagReading, veil, chipFill,
// subShade, subInk, subHl, vignette, phone.
const W = 1080, H = 1920, CX = W / 2, CY = H / 2;
const SUB_Y = 1440;
const cv = document.getElementById('c');
const MAIN = cv.getContext('2d');
let ctx = MAIN;
const TL = window.TIMELINE;
const S = TL.scenes;
const NAMED = S.filter(s => s.name);

const FT = {
  ui: '"Source Han Sans CN", "PingFang SC", sans-serif',
  mono: '"SF Mono", "Menlo", "Source Han Sans CN", monospace',
};
const pad2 = n => String(n).padStart(2, '0');

// ---------- utils ----------
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const E = {
  inOut: t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  out: t => 1 - Math.pow(1 - t, 3),
  in: t => t * t * t,
  back: t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
};
// the fractional part, in [0, 1) for negative x too: x % 1 is negative there, and a scene fading in is drawn at a negative
// local time (lt), so a cycle written lt * k % 1 goes below zero (大理: the first full render ran 20 minutes and died on a
// fade-in frame, a negative modulo used as a gradient stop). mod(a, n) is the same for a list index that cycles.
const frac = x => x - Math.floor(x);
const mod = (a, n) => ((a % n) + n) % n;
const prog = (t, s, d) => clamp((t - s) / d);
const fin = (t, s, d = .6) => E.out(prog(t, s, d));
const fout = (t, s, d = .6) => 1 - E.inOut(prog(t, s, d));
const pulse = (t, s, d) => Math.sin(Math.PI * prog(t, s, d));
const between = (t, a, b, f = .4) => fin(t, a, f) * fout(t, b, f);
const pop = (t, s, d = .45) => E.back(prog(t, s, d));
function rng(seed) { let a = seed | 0; return () => { a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hexA(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
function mixHex(h1, h2, p) {
  const a = parseInt(h1.slice(1), 16), b = parseInt(h2.slice(1), 16);
  const r = Math.round(lerp(a >> 16, b >> 16, p)), g = Math.round(lerp((a >> 8) & 255, (b >> 8) & 255, p)), bl = Math.round(lerp(a & 255, b & 255, p));
  return '#' + ((1 << 24) + (r << 16) + (g << 8) + bl).toString(16).slice(1);
}
function track(t, keys) {
  if (t <= keys[0][0]) return keys[0].slice(1);
  for (let i = 0; i < keys.length - 1; i++) {
    const [t0, ...a] = keys[i], [t1, ...b] = keys[i + 1];
    if (t <= t1) { const p = E.inOut(clamp((t - t0) / Math.max(1e-6, t1 - t0))); return a.map((v, j) => lerp(v, b[j], p)); }
  }
  return keys[keys.length - 1].slice(1);
}
// cue access: c/e = start/end, sp = time the part after a '|' pause starts, w = time a substring is spoken (n-th occurrence)
function Q(sc) {
  const m = {}; sc.cues.forEach(c => m[c.k] = c);
  const g = k => { if (!m[k]) throw new Error('no cue ' + k); return m[k]; };
  return {
    c: k => g(k).start, e: k => g(k).end,
    sp: (k, i = 0) => { const c = g(k); return c.splits.length > i ? c.splits[i] : c.start; },
    w: (k, s, n = 0) => {
      const c = g(k); let i = -1;
      for (let j = 0; j <= n; j++) { i = c.text.indexOf(s, i + 1); if (i < 0) throw new Error(`no "${s}" in ${k}`); }
      return c.ct[i];
    },
  };
}

// ---------- text and the legibility audit ----------
function txt(s, x, y, o = {}) {
  ctx.save();
  ctx.font = o.font || `400 40px ${FT.ui}`;
  ctx.fillStyle = o.color || K.ink;
  ctx.textAlign = o.align || 'center';
  ctx.textBaseline = o.base || 'middle';
  if (o.ls) { ctx.letterSpacing = o.ls + 'px'; if ((o.align || 'center') === 'center') x += o.ls / 2; }
  ctx.globalAlpha *= (o.alpha ?? 1);
  if (o.glow) { ctx.shadowColor = o.glowColor || o.color || K.ink; ctx.shadowBlur = o.glow; }
  ctx.fillText(s, x, y);
  if (window.AUDIT && !o.deco) {
    const px = fontPx(ctx.font), w = ctx.measureText(s).width, al = ctx.textAlign, bl = ctx.textBaseline;
    const x0 = al === 'center' ? x - w / 2 : (al === 'right' || al === 'end') ? x - w : x;
    const y0 = bl === 'middle' ? y - px / 2 : bl === 'top' ? y : bl === 'bottom' ? y - px : y - px * .8;
    audit(s, px, ctx.globalAlpha, [x0, y0, x0 + w, y0 + px]);
  }
  ctx.restore();
}
// when window.AUDIT is an array, every visible piece of text records its on-screen size and box (capture.mjs audit
// flags small text and text drawn over text)
function audit(s, px, alpha, box) {
  if (!window.AUDIT || ctx !== MAIN || alpha < .35 || !s || !String(s).trim()) return;
  const m = ctx.getTransform(), k = Math.sqrt(Math.abs(m.a * m.d - m.b * m.c));
  let b = null;
  if (box) {
    const cx = (box[0] + box[2]) / 2, cy = (box[1] + box[3]) / 2, X = m.a * cx + m.c * cy + m.e, Y = m.b * cx + m.d * cy + m.f;
    const hw = Math.abs(box[2] - box[0]) * k / 2, hh = Math.abs(box[3] - box[1]) * k / 2;
    b = [X - hw, Y - hh, X + hw, Y + hh];
    if (AUD.clip) { const v = isect(b, AUD.clip); if (area(v) < .3 * area(b)) return; b = v; }
    b = b.map(Math.round);
  }
  window.AUDIT.push([String(s), Math.round(px * k), +alpha.toFixed(2), b, AUD.scene]);
}
function auditCover(x, y, w, h, k) {
  if (window.AUDIT && ctx === MAIN && k > .05) window.AUDIT.push(['#cover', 0, +k.toFixed(2), scrBox(x, y, w, h).map(Math.round)]);
}
const AUD = { stack: [], clip: null, last: null, scene: -1 };
const isect = (p, q) => [Math.max(p[0], q[0]), Math.max(p[1], q[1]), Math.min(p[2], q[2]), Math.min(p[3], q[3])];
const area = r => Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]);
function scrBox(x, y, w, h) {
  const m = ctx.getTransform(), p = [[x, y], [x + w, y], [x, y + h], [x + w, y + h]].map(([u, v]) => [m.a * u + m.c * v + m.e, m.b * u + m.d * v + m.f]);
  return [Math.min(...p.map(q => q[0])), Math.min(...p.map(q => q[1])), Math.max(...p.map(q => q[0])), Math.max(...p.map(q => q[1]))];
}
{ // while auditing, follow clip regions (every clip here is a rect or roundRect) so text scrolled out of view does not count
  const o = { save: MAIN.save, restore: MAIN.restore, clip: MAIN.clip, rect: MAIN.rect, roundRect: MAIN.roundRect };
  MAIN.save = function () { o.save.call(MAIN); if (window.AUDIT) AUD.stack.push(AUD.clip); };
  MAIN.restore = function () { o.restore.call(MAIN); if (window.AUDIT) AUD.clip = AUD.stack.length ? AUD.stack.pop() : null; };
  MAIN.rect = function (x, y, w, h) { o.rect.call(MAIN, x, y, w, h); if (window.AUDIT) AUD.last = scrBox(x, y, w, h); };
  MAIN.roundRect = function (x, y, w, h, r) { o.roundRect.call(MAIN, x, y, w, h, r); if (window.AUDIT) AUD.last = scrBox(x, y, w, h); };
  MAIN.clip = function (...a) { o.clip.apply(MAIN, a); if (window.AUDIT && AUD.last) AUD.clip = AUD.clip ? isect(AUD.clip, AUD.last) : AUD.last; };
}
// the people on screen (person(), chibi(), a film's own figures): capture.mjs audit checks subtitles running over them and
// people cut by the frame edge (等于没说: the subtitles sat on the doll in front, dolls stood half out of the frame)
function subject(name, box, a = 1) {   // box in screen pixels [x0, y0, x1, y1]
  if (window.AUDIT && ctx === MAIN && a >= .5) window.AUDIT.push(['#subject:' + name, 0, +a.toFixed(2), box.map(Math.round), AUD.scene]);
}
function subjectLocal(name, x, y, w, h, a = 1) { if (window.AUDIT && ctx === MAIN) subject(name, scrBox(x, y, w, h), a); }
const fontPx = f => +((/(\d+(?:\.\d+)?)px/.exec(f) || [0, 40])[1]);   // a size can be fractional (120.879px is not 879px)
function tw(s, font) { ctx.save(); ctx.font = font; const w = ctx.measureText(s).width; ctx.restore(); return w; }
function line(x1, y1, x2, y2, color, w = 2, alpha = 1, dash) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = 'round';
  if (dash) ctx.setLineDash(dash);
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.restore();
}
function circle(x, y, r, fill, alpha = 1, stroke, lw = 2) {
  ctx.save(); ctx.globalAlpha *= alpha; ctx.beginPath(); ctx.arc(x, y, Math.max(0, r), 0, Math.PI * 2);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
  ctx.restore();
}
function glow(x, y, r, color, a = 1, add = true) {
  if (a <= 0 || r <= 0) return;
  ctx.save(); ctx.globalAlpha *= Math.min(1, a); if (add) ctx.globalCompositeOperation = 'lighter';
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, hexA(color, .8)); g.addColorStop(.3, hexA(color, .3)); g.addColorStop(1, hexA(color, 0));
  ctx.fillStyle = g; ctx.fillRect(x - r, y - r, r * 2, r * 2); ctx.restore();
}
function rr(x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
// characters fade in one after another between t0 and t1
function reveal(s, x, y, lt, t0, t1, o = {}) {
  if (lt < t0 - .02) return;
  const a0 = o.alpha ?? 1; if (a0 <= 0) return;
  const chars = [...s], size = o.size ?? 48, font = `${o.weight ?? 500} ${size}px ${FT.ui}`;
  ctx.save(); ctx.font = font; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  const ls = o.ls ?? 0, ws = chars.map(c => ctx.measureText(c).width);
  const total = ws.reduce((p, q) => p + q, 0) + ls * (chars.length - 1);
  let cx = o.align === 'left' ? x : o.align === 'right' ? x - total : x - total / 2;
  const bx0 = cx, base = ctx.globalAlpha, per = Math.max(.2, t1 - t0) / chars.length;
  let shown = 0, bx1 = cx;
  if (o.glow) { ctx.shadowColor = o.glowColor || (typeof o.color === 'string' ? o.color : K.ink); ctx.shadowBlur = o.glow; }
  for (let i = 0; i < chars.length; i++) {
    const k = clamp((lt - (t0 + i * per)) / Math.max(.1, per * 1.6));
    if (k > 0) {
      ctx.globalAlpha = base * a0 * E.out(k);
      ctx.fillStyle = typeof o.color === 'function' ? o.color(i, chars[i]) : (o.color || K.ink);
      ctx.fillText(chars[i], cx, y + (1 - E.out(k)) * size * .18);
      if (k > .5) { shown = i + 1; bx1 = cx + ws[i]; }
    }
    cx += ws[i] + ls;
  }
  ctx.globalAlpha = base * a0;
  if (shown) audit(chars.slice(0, shown).join(''), size, base * a0, [bx0, y - size / 2, bx1, y + size / 2]);
  ctx.restore();
}

// ---------- small pieces ----------
function panel(x, y, w, h, a = 1, o = {}) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  rr(x, y, w, h, o.r ?? 24); ctx.fillStyle = o.fill || K.panel; ctx.fill();
  if (o.edge !== false) { ctx.lineWidth = o.lw ?? 2; ctx.strokeStyle = o.edge || K.edge; ctx.stroke(); }
  ctx.restore();
  if (o.cover !== false) auditCover(x, y, w, h, (o.k ?? .6) * a);
}
// a small label in a rounded pill; returns its width
function pill(s, x, y, o = {}) {
  const size = o.size ?? 38, font = `${o.weight ?? 500} ${size}px ${FT.ui}`, col = o.color || K.ink;
  const w = tw(s, font) + size * 1.2, h = Math.round(size * 1.6);
  const x0 = o.align === 'right' ? x - w : o.align === 'left' ? x : x - w / 2;
  const a = o.alpha ?? 1; if (a <= 0) return w;
  ctx.save(); ctx.globalAlpha *= a;
  rr(x0, y - h / 2, w, h, h / 2); ctx.fillStyle = o.fill || K.pillFill || 'rgba(10,14,26,.82)'; ctx.fill();
  ctx.lineWidth = 2; ctx.strokeStyle = o.stroke || hexA(col.length === 7 ? col : K.ink, .85); ctx.stroke();
  ctx.restore();
  txt(s, x0 + w / 2, y + 1, { font, color: o.textColor || col, alpha: a, deco: o.deco });
  return w;
}
// the fixed markers, the same all through a film: something research found, and a reading of ours
function researchTag(x, y, a, align = 'left') { if (a > 0) pill('有研究', x, y, { color: K.tagResearch || '#E2E6EE', alpha: a, size: 38, align }); }
function readingTag(x, y, a, align = 'left') { if (a > 0) pill('一种读法', x, y, { color: K.tagReading || K.lav, alpha: a, size: 38, align }); }
function checkMark(x, y, s, col, a = 1, p = 1) {
  if (a <= 0 || p <= 0) return;
  const P = [[-.45, 0], [-.12, .33], [.48, -.36]].map(([u, v]) => [x + u * s, y + v * s]);
  const L1 = Math.hypot(P[1][0] - P[0][0], P[1][1] - P[0][1]), L2 = Math.hypot(P[2][0] - P[1][0], P[2][1] - P[1][1]);
  const d = clamp(p) * (L1 + L2);
  ctx.save(); ctx.globalAlpha *= a; ctx.strokeStyle = col; ctx.lineWidth = Math.max(3, s * .14); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(...P[0]);
  if (d <= L1) ctx.lineTo(lerp(P[0][0], P[1][0], d / L1), lerp(P[0][1], P[1][1], d / L1));
  else { ctx.lineTo(...P[1]); const k = (d - L1) / L2; ctx.lineTo(lerp(P[1][0], P[2][0], k), lerp(P[1][1], P[2][1], k)); }
  ctx.stroke(); ctx.restore();
}

// ---------- people: front view, real proportions ----------
// head ≈ 1/7 of the height, hips at half, thighs thicker than calves, arms thinner than legs.
// Angles in radians from straight down, + toward screen right. A pose: arms aL/aR and legs lL/lR as [upper, bend].
const P = {
  stand: { aL: [-.14, .06], aR: [.14, -.06], lL: [-.05, 0], lR: [.05, 0], lean: 0, tilt: 0 },
  pose: { aL: [-.75, 1.9], aR: [2.3, 1.75], lL: [-.03, 0], lR: [.2, -.06], lean: .03, tilt: .08 },
  point: { aL: [-.75, 1.9], aR: [1.45, -.12], lL: [-.06, 0], lR: [.12, 0], lean: -.03, tilt: .14 },
  shoot: { aL: [-1.9, .15], aR: [.14, -.06], lL: [-.08, 0], lR: [.08, 0], lean: -.02, tilt: -.1 },
  shrug: { aL: [-.55, -1.5], aR: [.55, 1.5], lL: [-.06, 0], lR: [.06, 0], lean: 0, tilt: .12 },
  laugh: { aL: [-.38, 1.05], aR: [.38, -1.05], lL: [-.07, 0], lR: [.07, 0], lean: -.05, tilt: -.25 },
  hold: { aL: [-.1, .05], aR: [.32, -.4], lL: [-.05, 0], lR: [.05, 0], lean: 0, tilt: 0 },
  hips: { aL: [-.75, 1.9], aR: [.75, -1.9], lL: [-.08, 0], lR: [.08, 0], lean: 0, tilt: 0 },
  cam: { aL: [-.5, 2.35], aR: [.5, -2.35], lL: [-.06, 0], lR: [.06, 0], lean: 0, tilt: 0 },   // both hands up at the face: a camera
};
function lerpPose(p1, p2, t) {
  const o = {};
  for (const k in p1) o[k] = Array.isArray(p1[k]) ? p1[k].map((v, i) => lerp(v, p2[k][i], t)) : lerp(p1[k], p2[k], t);
  return o;
}
const dirv = th => [Math.sin(th), Math.cos(th)];
function blob(x1, y1, x2, y2, w1, w2) {   // a tapered limb: a quad with round ends, filled with the current fillStyle
  const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L;
  ctx.beginPath(); ctx.moveTo(x1 + nx * w1 / 2, y1 + ny * w1 / 2); ctx.lineTo(x2 + nx * w2 / 2, y2 + ny * w2 / 2);
  ctx.lineTo(x2 - nx * w2 / 2, y2 - ny * w2 / 2); ctx.lineTo(x1 - nx * w1 / 2, y1 - ny * w1 / 2); ctx.closePath(); ctx.fill();
  ctx.beginPath(); ctx.arc(x1, y1, w1 / 2, 0, 7); ctx.fill(); ctx.beginPath(); ctx.arc(x2, y2, w2 / 2, 0, 7); ctx.fill();
}
// (x, y) = between the feet on the ground, h = height. Returns where the hands and head are.
function person(x, y, h, o = {}) {
  const a = o.a ?? 1; if (a <= 0) return null;
  if (!o.bg) subjectLocal('人', x - h * .16, y - h, h * .32, h, a * ctx.globalAlpha);   // o.bg: a figure in a veiled background, not checked
  const f = o.sex === 'f', u = h / 100, pz = o.pose || P.stand, col = o.col || K.ink, edge = o.edge || K.bg0, e = Math.max(1.2, .9 * u);
  const bob = o.bob ?? 0;
  ctx.save(); ctx.globalAlpha *= a; ctx.translate(x, y); ctx.rotate(pz.lean || 0); ctx.translate(0, -bob * u);
  const hipY = -50 * u, waistY = -62 * u, shY = -81 * u, headR = 7.2 * u, headC = -92.6 * u;
  const shW = (f ? 10.2 : 12.4) * u, hipW = (f ? 9.4 : 8.4) * u, waistW = (f ? 6.4 : 8) * u;
  const two = (fn) => { ctx.fillStyle = edge; fn(e); ctx.fillStyle = col; fn(0); };
  // legs
  const leg = (side, [th, bend]) => {
    const hx = side * hipW * .52, hy = hipY + 2 * u, [d1x, d1y] = dirv(th), [d2x, d2y] = dirv(th + bend);
    const kx = hx + d1x * 24.5 * u, ky = hy + d1y * 24.5 * u, ax = kx + d2x * 23 * u, ay = ky + d2y * 23 * u;
    two(g => { blob(hx, hy, kx, ky, (f ? 7.2 : 8.8) * u + 2 * g, (f ? 5.2 : 6.0) * u + 2 * g); blob(kx, ky, ax, ay, (f ? 5.4 : 5.2) * u + 2 * g, 3.1 * u + 2 * g);
      ctx.beginPath(); ctx.ellipse(ax + side * 2.2 * u, ay + 1.2 * u, 4.2 * u + g, 1.9 * u + g, 0, 0, 7); ctx.fill(); });
  };
  if (f && o.hair !== false) two(g => { // long hair, behind
    rr(-headR * 1.12 - g, headC - 2 * u - g, headR * 2.24 + 2 * g, 19 * u + 2 * g, headR); ctx.fill();
  });
  leg(-1, pz.lL); leg(1, pz.lR);
  // torso
  two(g => {
    ctx.beginPath(); ctx.moveTo(-shW - g, shY - g); ctx.lineTo(shW + g, shY - g); ctx.lineTo(waistW + g, waistY); ctx.lineTo(hipW + g, hipY + 3 * u + g);
    ctx.lineTo(-hipW - g, hipY + 3 * u + g); ctx.lineTo(-waistW - g, waistY); ctx.closePath(); ctx.fill();
    ctx.beginPath(); ctx.arc(-shW + 2 * u, shY + 2 * u, 3.4 * u + g, 0, 7); ctx.fill(); ctx.beginPath(); ctx.arc(shW - 2 * u, shY + 2 * u, 3.4 * u + g, 0, 7); ctx.fill();
  });
  if (f) two(g => {   // a dress: from the waist to just above the knee
    ctx.beginPath(); ctx.moveTo(-waistW - g, waistY - 1 * u); ctx.lineTo(waistW + g, waistY - 1 * u); ctx.lineTo(hipW * 1.65 + g, -29 * u + g); ctx.lineTo(-hipW * 1.65 - g, -29 * u + g); ctx.closePath(); ctx.fill();
  });
  // arms
  const hands = {};
  const arm = (side, [th, bend], key) => {
    const sx = side * (shW - 1.4 * u), sy = shY + 2.2 * u, [d1x, d1y] = dirv(th), [d2x, d2y] = dirv(th + bend);
    const ex = sx + d1x * 16.5 * u, ey = sy + d1y * 16.5 * u, wx = ex + d2x * 14.5 * u, wy = ey + d2y * 14.5 * u;
    two(g => { blob(sx, sy, ex, ey, 4.6 * u + 2 * g, 3.7 * u + 2 * g); blob(ex, ey, wx, wy, 3.7 * u + 2 * g, 2.8 * u + 2 * g); ctx.beginPath(); ctx.arc(wx + d2x * 1.6 * u, wy + d2y * 1.6 * u, 2.3 * u + g, 0, 7); ctx.fill(); });
    hands[key] = [wx + d2x * 2 * u, wy + d2y * 2 * u];
  };
  arm(-1, pz.aL, 'L'); arm(1, pz.aR, 'R');
  // neck and head
  ctx.save(); ctx.translate(0, shY); ctx.rotate(pz.tilt || 0); ctx.translate(0, -shY);
  two(g => { rr(-2.4 * u - g, headC + 4 * u, 4.8 * u + 2 * g, shY - headC - 2 * u, 2 * u); ctx.fill(); ctx.beginPath(); ctx.arc(0, headC, headR + g, 0, 7); ctx.fill(); });
  if (f) two(g => { ctx.beginPath(); ctx.ellipse(0, headC - 2.2 * u, headR * 1.08 + g, headR * .78 + g, 0, Math.PI, 0); ctx.fill(); });   // fringe
  else two(g => { ctx.beginPath(); ctx.ellipse(0, headC - 2.4 * u, headR * 1.04 + g, headR * .66 + g, 0, Math.PI, 0); ctx.fill(); });     // short hair
  ctx.restore();
  // what the hands hold
  if (o.phone) { const [px, py] = hands[o.phone]; ctx.save(); ctx.translate(px, py); ctx.rotate(o.phoneRot ?? 0); rr(-4.2 * u, -7 * u, 8.4 * u, 14 * u, 1.4 * u); ctx.fillStyle = K.phone || '#1D2337'; ctx.fill(); ctx.lineWidth = Math.max(2, .7 * u); ctx.strokeStyle = K.ink; ctx.stroke(); ctx.restore(); }
  if (o.held) { ctx.save(); o.held(hands, u); ctx.restore(); }   // anything else in the hands: the film draws it, in the person's own coordinates
  ctx.restore();
  const g2s = ([hx, hy]) => { const c = Math.cos(pz.lean || 0), s_ = Math.sin(pz.lean || 0), yy = hy - bob * u; return [x + hx * c - yy * s_, y + hx * s_ + yy * c]; };
  return { L: g2s(hands.L), R: g2s(hands.R), head: g2s([0, headC]), top: g2s([0, headC - headR]) };
}

// ---------- type: spoken lines shown big instead of subtitles; the question at the end of a chapter ----------
function bigLines(lines, lt, t0, t1, y, o = {}) {
  const a = o.alpha ?? 1; if (a <= 0) return;
  if (o.veil) {   // a dark band behind the words only: from just above the first line to just below the last
    const lastY = y + lines.slice(0, -1).reduce((p, l) => p + l[1] * 1.5, 0), top = y - 120, bot = lastY + 95;
    const vc = K.veil || '9,12,23', g = ctx.createLinearGradient(0, top, 0, bot); g.addColorStop(0, `rgba(${vc},0)`); g.addColorStop(.25, `rgba(${vc},${.78 * a})`); g.addColorStop(.75, `rgba(${vc},${.78 * a})`); g.addColorStop(1, `rgba(${vc},0)`);
    ctx.fillStyle = g; ctx.fillRect(0, top, W, bot - top); auditCover(0, top + 30, W, bot - top - 60, .7 * a);
  }
  const total = lines.reduce((p, l) => p + [...l[0]].length, 0); let acc = 0;
  for (const [s, size, color] of lines) {
    const n = [...s].length, s0 = t0 + (t1 - t0) * acc / total, s1 = t0 + (t1 - t0) * (acc + n) / total;
    reveal(s, CX, y, lt, s0 - .05, s1, { size, weight: o.weight ?? 700, color: color || K.ink, alpha: a });
    acc += n; y += size * 1.5;
  }
}
function question(lines, lt, t0, t1, o = {}) {
  const a = fin(lt, t0 - .35, .45) * (o.alpha ?? 1);
  if (a <= 0) return 0;
  const vh = o.veil ?? 640;
  const vc = K.veil || '9,12,23', g = ctx.createLinearGradient(0, 0, 0, vh);
  g.addColorStop(0, `rgba(${vc},${.92 * a})`); g.addColorStop(.62, `rgba(${vc},${.72 * a})`); g.addColorStop(1, `rgba(${vc},0)`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, vh);
  auditCover(0, 0, W, vh * .8, .7 * a);
  let y = o.y ?? 320; const total = lines.reduce((p, l) => p + [...l].length, 0); let acc = 0;
  lines.forEach((l, i) => {
    const n = [...l].length, s0 = t0 + (t1 - t0) * acc / total, s1 = t0 + (t1 - t0) * (acc + n) / total, size = (o.sizes || [])[i] ?? 66;
    reveal(l, CX, y, lt, s0 - .05, s1, { size, weight: 600, alpha: a, color: K.ink });
    acc += n; y += Math.max(98, size * 1.5);
  });
  return a;
}

function drawScene(k, lt, alpha = 1) {
  if (alpha <= 0) return;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  AUD.scene = k; SCENE_FN[S[k].id](lt, S[k]); AUD.scene = -1;
  ctx.restore();
}
function chapterTag(t) {
  NAMED.forEach((s, i) => {
    const lt = t - s.start, len = (s.out ?? s.end) - s.start;
    if (lt < 0 || lt > len) return;
    const a = fin(lt, .5, .6) * fout(lt, len - .4, .4);
    if (a <= 0) return;
    const font = `500 38px ${FT.ui}`, w = 104 + tw(s.name, font) + 34;
    ctx.save(); ctx.globalAlpha = .9 * a; ctx.fillStyle = K.chipFill || '#0A0E1B'; rr(34, 150, w, 64, 32); ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = K.edge; ctx.stroke(); ctx.restore();
    auditCover(34, 150, w, 64, .9 * a);
    if (window.AUDIT) window.AUDIT.push(['#chip', 0, a, [34, 150, 34 + w, 214]]);
    txt(pad2(i + 1), 64, 182, { font: `400 36px ${FT.mono}`, color: K.dim, alpha: a, align: 'left' });
    txt(s.name, 124, 182, { font, color: K.ink, alpha: a, align: 'left', ls: 4 });
  });
}

// ---------- subtitles and finish ----------
// a highlighted subtitle word takes the colour of what it means (the film's HL/HLC); anything else gets K.subHl
function hlColor(s) { if (typeof HL !== 'undefined') for (const [w, k] of HL) if (s.includes(w)) return HLC[k]; return K.subHl || '#A9D8FF'; }
function drawSubLine(s, hl, a) {
  let size = 58; const font = sz => `500 ${sz}px ${FT.ui}`;
  ctx.save(); ctx.font = font(size); let w = ctx.measureText(s).width;
  if (w > 860) { size = Math.floor(size * 860 / w); ctx.font = font(size); w = ctx.measureText(s).width; }
  const chars = [...s]; const ws = chars.map(c => ctx.measureText(c).width);
  const x0 = CX - ws.reduce((p, q) => p + q, 0) / 2;
  const band = ctx.createLinearGradient(0, SUB_Y - 90, 0, SUB_Y + 90);
  const sc = K.subShade || '6,8,14';
  band.addColorStop(0, `rgba(${sc},0)`); band.addColorStop(.5, `rgba(${sc},${.42 * a})`); band.addColorStop(1, `rgba(${sc},0)`);
  ctx.fillStyle = band; ctx.fillRect(0, SUB_Y - 90, W, 180);
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.lineJoin = 'round'; ctx.globalAlpha = a;
  ctx.strokeStyle = `rgba(${sc},.9)`; ctx.lineWidth = 12;
  let x = x0; chars.forEach((c, i) => { ctx.strokeText(c, x, SUB_Y); x += ws[i]; });
  const cols = hl.map(([p, q]) => [p, q, hlColor(s.slice(p, q))]);
  x = x0; chars.forEach((c, i) => { const h = cols.find(([p, q]) => i >= p && i < q); ctx.fillStyle = h ? h[2] : (K.subInk || '#FFFFFF'); ctx.fillText(c, x, SUB_Y); x += ws[i]; });
  audit('〔字幕〕' + s, size, a, [x0, SUB_Y - size / 2, x, SUB_Y + size / 2]);
  ctx.restore();
}
function drawSubs(t) {
  for (const sc of S) {
    const lt = t - sc.start;
    for (const c of sc.cues) {
      if (lt < c.start - .2 || lt > c.end + .4) continue;
      for (const ch of c.subs) {
        if (lt < ch.t0 - .03 || lt > ch.t1 - .03) continue;
        drawSubLine(ch.s, ch.hl, Math.min(clamp((lt - (ch.t0 - .03)) / .06), clamp((ch.t1 - .03 - lt) / .06)));
      }
    }
  }
}
let GRAIN = [];
function buildGrain() {
  for (let g = 0; g < 4; g++) {
    const c = document.createElement('canvas'); c.width = 540; c.height = 960;
    const x = c.getContext('2d'); const id = x.createImageData(540, 960); const r = rng(1000 + g);
    for (let i = 0; i < id.data.length; i += 4) { const v = r() * 255; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255; }
    x.putImageData(id, 0, 0); GRAIN.push(c);
  }
}
function drawFinish(t) {
  const dim = typeof finishDim === 'function' ? finishDim(t) : 1, vc = K.vignette || '6,8,16';   // a film can lift the vignette, e.g. over a bright end card
  const g = ctx.createRadialGradient(CX, H / 2, H * .36, CX, H / 2, H * .8);
  g.addColorStop(0, `rgba(${vc},0)`); g.addColorStop(1, `rgba(${vc},${.32 * dim})`);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalAlpha = .045; ctx.globalCompositeOperation = 'overlay';
  ctx.drawImage(GRAIN[mod(Math.floor(t * 30), 4)], 0, 0, W, H); ctx.restore();
  // the fade up from black at the start: a film sets FADE_IN = 0 to open on a lit first frame (in a Douyin feed the first frame is the cover)
  const fi = typeof FADE_IN === 'number' ? FADE_IN : .5;
  const a = Math.max(fi > 0 ? 1 - clamp(t / fi) : 0, clamp((t - (TL.duration - 1.4)) / 1.4));
  if (a > 0) { ctx.fillStyle = `rgba(0,0,0,${a})`; ctx.fillRect(0, 0, W, H); auditCover(0, 0, W, H, a); }
}

window.renderFrame = function (t) {
  ctx = MAIN;
  AUD.stack = []; AUD.clip = null; AUD.last = null; AUD.scene = -1;
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.filter = 'none';
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
  let k = S.length - 1, tr = null;
  for (let i = 0; i < S.length - 1; i++) {
    const s = S[i]; const d = TL.trans[s.trans];
    if (t < s.out) { k = i; break; }
    if (t < s.out + d) { k = i; tr = { type: s.trans, p: (t - s.out) / d }; break; }
  }
  if (!tr) drawScene(k, t - S[k].start);
  else if (typeof TRANSITIONS !== 'undefined' && TRANSITIONS[tr.type]) TRANSITIONS[tr.type](k, t, tr.p);   // the film's own (text drawn by it is audited as scene 100 + k)
  else {   // a dissolve that dips through the dark: the old scene goes before the new one comes up, no double image
    const a0 = 1 - E.inOut(clamp(tr.p * 2)), a1 = E.inOut(clamp(tr.p * 2 - 1));
    if (a0 > 0) drawScene(k, t - S[k].start, a0);
    if (a1 > 0) drawScene(k + 1, t - S[k + 1].start, a1);
  }
  if (!tr) chapterTag(t);
  drawSubs(t);
  drawFinish(t);
};

window.ready = (async () => {
  const specs = [`300 40px ${FT.ui}`, `400 40px ${FT.ui}`, `500 40px ${FT.ui}`, `600 40px ${FT.ui}`, `700 40px ${FT.ui}`, `800 40px ${FT.ui}`, `40px ${FT.mono}`];
  const sample = [...new Set(S.map(s => s.name + s.cues.map(c => c.text).join('')).join('') + '追本')].join('');
  try { await Promise.all(specs.map(s => document.fonts.load(s, sample))); } catch (e) { }
  buildGrain();
  return true;
})();
