// 像素画法，各片共用（试样在 设计/像素/）。index.html 在 film.js 之后载入，render.js 之前。
// 世界画在一张小画布上（每格一个像素），整张放大贴到屏幕上，放大时不平滑；字画在全分辨率上（伤害数字、对话框、字幕）。
// 精灵用色块拼，最后自动描一圈一像素的深色边。主角就是 lib/chibi.js 那个少年冒险家（配色 C）的像素版。
//   heroFront(face, arms, wig)   正面，30×34。face: calm | dead | laugh | think | happy | puzzled
//                                arms: side | tickle | up | palm | look | lever | wave | poke；wig 让手抖一像素
//   heroSide(press, face)        侧面朝右，25×34，press 0..1 把食指往前推；face: calm | laugh | determined
//   otherSide(press, face)       配角侧面（盘发、眼镜、灰蓝卫衣），画的时候 flip 成朝左；face: calm | sad | determined
//   pBuddy(face, antenna)        问问，16×20；face: calm | happy；antenna: up | curl（问号）| droop（戳人）
//   blit(g, sprite, x, y, flip)  画到世界画布上；world(w, h) 新建一张世界画布；paintWorld(world, x, y, px) 放大贴到屏幕
//   pt(s, x, y, size, o)         游戏字：硬投影加深色描边，填色那一层走 film.js 的 txt()，字号、叠字检查照旧
//   pixBox(x, y, w, h, a, fill)  游戏窗口：深色底，一圈双线像素边
const PIX = {
  k: '#1F1A24', c: '#F4EEE2', y: '#D98A24', t: '#2F8C87', h: '#3B3245', s: '#FFD5B5', e: '#1F1A24', w: '#FFFFFF', b: '#FF9A8A',
  j: '#F2A63A', u: '#F6F1E8', p: '#4B5A6E', o: '#F6F1E8', n: '#7A5236', r: '#E8747C',
  m: '#8FD3C1', f: '#FFF3D9', Y: '#F2A63A', q: '#5B4337', v: '#8FA1B5', V: '#73869B', g: '#1F1A24',
};
function pgrid(w, h) { return { w, h, d: Array.from({ length: h }, () => Array(w).fill(null)) }; }
function pR(s, x, y, w, h, c) { for (let j = y; j < y + h; j++) for (let i = x; i < x + w; i++) if (i >= 0 && j >= 0 && i < s.w && j < s.h) s.d[j][i] = c; }
function pOutline(s, c = 'k') {
  const add = [];
  for (let y = 0; y < s.h; y++) for (let x = 0; x < s.w; x++) {
    if (s.d[y][x]) continue;
    if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => s.d[y + dy] && s.d[y + dy][x + dx] && s.d[y + dy][x + dx] !== c)) add.push([x, y]);
  }
  add.forEach(([x, y]) => s.d[y][x] = c); return s;
}
function blit(g, s, x, y, flip = false, alpha = 1) {
  if (alpha <= 0) return;
  g.save(); g.globalAlpha *= alpha; x = Math.round(x); y = Math.round(y);
  for (let j = 0; j < s.h; j++) for (let i = 0; i < s.w; i++) {
    const c = s.d[j][flip ? s.w - 1 - i : i]; if (!c) continue;
    g.fillStyle = PIX[c] || c; g.fillRect(x + i, y + j, 1, 1);
  }
  g.restore();
}
const pen = (s, ox, oy) => [(x, y, w, h, c) => pR(s, x + ox, y + oy, w, h, c), (x, y, c) => pR(s, x + ox, y + oy, 1, 1, c)];

function heroFront(face = 'calm', arms = 'side', wig = 0) {
  const s = pgrid(30, 34), [r, p] = pen(s, 4, 1);
  if (arms === 'up') { r(2, 13, 3, 6, 'j'); r(17, 13, 3, 6, 'j'); r(2, 18, 3, 1, 'y'); r(17, 18, 3, 1, 'y'); r(2, 11, 3, 2, 's'); r(17, 11, 3, 2, 's'); }
  if (arms === 'wave') { r(17 + wig, 13, 3, 6, 'j'); r(17 + wig, 18, 3, 1, 'y'); r(17 + wig, 11, 3, 2, 's'); }
  // cap
  r(7, 0, 8, 1, 'c'); r(5, 1, 12, 1, 'c'); r(4, 2, 14, 1, 'c'); r(3, 3, 16, 1, 'c'); r(10, 1, 2, 3, 't'); p(10, 3, 'w');
  r(2, 4, 18, 1, 'y'); r(3, 5, 16, 1, 'y');
  // hair under the brim, spiky at the sides
  r(2, 6, 18, 1, 'h'); r(1, 7, 4, 1, 'h'); r(17, 7, 4, 1, 'h'); r(2, 8, 3, 1, 'h'); r(17, 8, 3, 1, 'h'); r(1, 9, 3, 1, 'h'); r(18, 9, 3, 1, 'h'); p(3, 10, 'h'); p(18, 10, 'h');
  // face
  r(5, 7, 12, 1, 's'); r(4, 8, 14, 7, 's'); r(5, 15, 12, 1, 's'); r(7, 16, 8, 1, 's');
  p(6, 7, 'h'); p(7, 7, 'h'); p(11, 7, 'h'); p(14, 7, 'h'); p(15, 7, 'h');
  p(3, 11, 's'); p(3, 12, 's'); p(18, 11, 's'); p(18, 12, 's');
  if (face === 'laugh') {
    p(7, 11, 'e'); p(8, 10, 'e'); p(9, 11, 'e'); p(12, 11, 'e'); p(13, 10, 'e'); p(14, 11, 'e');
    r(9, 13, 4, 2, 'e'); p(10, 14, 'r'); p(11, 14, 'r'); r(5, 12, 2, 1, 'b'); r(15, 12, 2, 1, 'b');
  } else if (face === 'happy') {
    p(7, 11, 'e'); p(8, 10, 'e'); p(9, 11, 'e'); p(12, 11, 'e'); p(13, 10, 'e'); p(14, 11, 'e');
    p(9, 13, 'e'); p(10, 14, 'e'); p(11, 14, 'e'); p(12, 13, 'e'); r(5, 12, 2, 1, 'b'); r(15, 12, 2, 1, 'b');
  } else if (face === 'dead') {
    r(7, 11, 2, 1, 'e'); r(13, 11, 2, 1, 'e'); r(10, 14, 2, 1, 'e');
  } else {
    r(7, 10, 2, 2, 'e'); p(8, 10, 'w'); r(13, 10, 2, 2, 'e'); p(14, 10, 'w'); r(5, 12, 2, 1, 'b'); r(15, 12, 2, 1, 'b');
    if (face === 'think') { p(11, 14, 'e'); p(12, 14, 'e'); }
    else if (face === 'puzzled') { p(11, 13, 'e'); p(11, 14, 'e'); p(12, 13, 'e'); p(12, 14, 'e'); }
    else { p(9, 13, 'e'); p(10, 14, 'e'); p(11, 14, 'e'); p(12, 13, 'e'); }
  }
  // body: open jacket over a white tee, collar, backpack straps
  r(6, 17, 10, 9, 'j'); r(5, 23, 12, 3, 'j'); r(10, 17, 2, 9, 'u'); r(8, 17, 2, 1, 'y'); r(12, 17, 2, 1, 'y'); r(7, 18, 1, 4, 'n'); r(14, 18, 1, 4, 'n');
  const leftSide = () => { r(3, 18, 3, 5, 'j'); r(3, 22, 3, 1, 'y'); r(3, 23, 3, 2, 's'); };
  const rightSide = () => { r(16, 18, 3, 5, 'j'); r(16, 22, 3, 1, 'y'); r(16, 23, 3, 2, 's'); };
  if (arms === 'side') { leftSide(); rightSide(); }
  if (arms === 'tickle') { leftSide(); r(16, 18, 3, 3, 'j'); r(12 + wig, 21, 5, 2, 'j'); r(11 + wig, 21, 1, 2, 'y'); r(8 + wig, 21, 3, 2, 's'); }
  if (arms === 'palm') { r(4, 18, 3, 3, 'j'); r(15, 18, 3, 3, 'j'); r(6, 21, 3, 2, 'j'); r(13, 21, 3, 2, 'j'); r(9, 20 + wig, 4, 2, 's'); }
  if (arms === 'look') { r(3, 18, 3, 2, 'j'); r(4, 15, 3, 3, 'j'); r(4, 14, 3, 1, 'y'); r(5 + wig, 12, 3, 2, 's'); rightSide(); }
  if (arms === 'lever') { r(2, 18, 3, 4, 'j'); r(1, 22, 3, 1, 'y'); r(0, 23, 3, 2, 's'); r(16, 19, 4, 2, 'j'); r(20, 19, 1, 2, 'y'); r(21, 18, 3, 2, 's'); }
  if (arms === 'wave') leftSide();
  if (arms === 'poke') { leftSide(); r(16, 19, 4 + wig, 2, 'j'); r(20 + wig, 19, 1, 2, 'y'); r(21 + wig, 19, 2, 2, 's'); p(23 + wig, 19, 's'); }
  // shorts, legs, shoes
  r(6, 26, 10, 2, 'p'); r(7, 28, 2, 2, 's'); r(13, 28, 2, 2, 's'); r(6, 30, 4, 2, 'o'); r(12, 30, 4, 2, 'o');
  return pOutline(s);
}
function heroSide(press = 0, face = 'calm') {
  const s = pgrid(25, 34), [r, p] = pen(s, 1, 1);
  r(4, 17, 3, 6, 'n');
  r(6, 0, 7, 1, 'c'); r(4, 1, 10, 1, 'c'); r(3, 2, 12, 2, 'c'); p(12, 2, 't'); p(12, 3, 't');
  r(3, 4, 12, 1, 'y'); r(13, 4, 7, 1, 'y'); r(14, 5, 5, 1, 'y');
  r(2, 5, 7, 6, 'h'); p(1, 6, 'h'); p(1, 8, 'h'); r(3, 11, 4, 2, 'h');
  r(8, 5, 6, 1, 's'); r(8, 6, 8, 9, 's'); p(16, 10, 's'); r(9, 15, 6, 1, 's'); p(9, 9, 's'); p(9, 10, 's');
  if (face === 'laugh') { p(12, 9, 'e'); p(13, 8, 'e'); p(14, 9, 'e'); r(13, 12, 2, 2, 'e'); }
  else if (face === 'determined') { r(13, 9, 2, 1, 'e'); p(12, 8, 'e'); p(14, 12, 'e'); p(15, 12, 'e'); }
  else { r(13, 8, 2, 2, 'e'); p(14, 8, 'w'); p(14, 12, 'e'); p(15, 12, 'e'); }
  r(11, 11, 2, 1, 'b');
  r(7, 16, 8, 10, 'j'); r(13, 16, 2, 10, 'u'); r(6, 23, 9, 3, 'j');
  const f = Math.round(press * 2);
  r(11, 18, 6 + f, 2, 'j'); r(17 + f, 18, 1, 2, 'y'); r(18 + f, 18, 2, 2, 's'); p(20 + f, 18, 's');
  r(7, 26, 8, 2, 'p'); r(8, 28, 2, 2, 's'); r(12, 28, 2, 2, 's'); r(8, 30, 4, 2, 'o'); r(12, 30, 4, 2, 'o');
  return pOutline(s);
}
function otherSide(press = 0, face = 'calm') {
  const s = pgrid(25, 34), [r, p] = pen(s, 1, 1);
  r(3, 0, 4, 3, 'q'); r(5, 2, 9, 2, 'q'); r(3, 4, 12, 2, 'q'); r(2, 6, 7, 7, 'q');
  r(8, 6, 8, 9, 's'); p(16, 10, 's'); r(9, 15, 6, 1, 's'); r(9, 5, 6, 1, 'q');
  if (face === 'sad') { r(13, 9, 2, 1, 'e'); p(14, 13, 'e'); p(13, 12, 'e'); p(15, 12, 'e'); }
  else if (face === 'determined') { r(13, 9, 2, 1, 'e'); p(12, 8, 'e'); p(14, 12, 'e'); p(15, 12, 'e'); }
  else { r(13, 8, 2, 2, 'e'); p(14, 8, 'w'); p(14, 12, 'e'); p(15, 12, 'e'); }
  r(12, 7, 4, 1, 'g'); p(12, 8, 'g'); p(15, 8, 'g'); p(12, 9, 'g'); p(15, 9, 'g'); r(12, 10, 4, 1, 'g'); r(9, 8, 3, 1, 'g');
  r(11, 11, 2, 1, 'b');
  r(7, 16, 8, 10, 'v'); r(5, 16, 4, 3, 'V'); r(6, 23, 9, 3, 'v');
  const f = Math.round(press * 2);
  r(11, 18, 6 + f, 2, 'v'); r(18 + f, 18, 2, 2, 's'); p(20 + f, 18, 's');
  r(7, 26, 8, 2, 'p'); r(8, 28, 2, 2, 's'); r(12, 28, 2, 2, 's'); r(8, 30, 4, 2, 'o'); r(12, 30, 4, 2, 'o');
  return pOutline(s);
}
function pBuddy(face = 'calm', antenna = 'up') {
  const s = pgrid(16, 20), [r, p] = pen(s, 1, 1);
  if (antenna === 'curl') { r(7, 3, 1, 3, 'm'); r(8, 2, 2, 1, 'm'); p(10, 3, 'm'); p(9, 4, 'm'); r(9, 0, 2, 2, 'Y'); }
  else if (antenna === 'droop') { r(8, 4, 3, 1, 'm'); p(11, 5, 'm'); r(11, 6, 2, 2, 'Y'); }
  else { r(7, 2, 1, 4, 'm'); r(6, 0, 3, 2, 'Y'); }
  r(4, 6, 6, 1, 'm'); r(2, 7, 10, 1, 'm'); r(1, 8, 12, 8, 'm'); r(2, 16, 10, 1, 'm');
  r(4, 11, 6, 4, 'f'); r(5, 15, 4, 1, 'f');
  if (face === 'happy') { p(3, 10, 'e'); p(4, 9, 'e'); p(5, 10, 'e'); p(8, 10, 'e'); p(9, 9, 'e'); p(10, 10, 'e'); r(6, 12, 2, 1, 'e'); }
  else { r(3, 9, 2, 2, 'e'); p(4, 9, 'w'); r(9, 9, 2, 2, 'e'); p(10, 9, 'w'); p(6, 12, 'e'); p(7, 12, 'e'); }
  p(2, 12, 'b'); p(11, 12, 'b');
  r(3, 17, 2, 1, 'm'); r(9, 17, 2, 1, 'm');
  return pOutline(s);
}

function world(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'); g.imageSmoothingEnabled = false; return { c, g, w, h }; }
function paintWorld(wd, x, y, px, a = 1) {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a; ctx.imageSmoothingEnabled = false; ctx.drawImage(wd.c, x, y, wd.w * px, wd.h * px); ctx.restore();
}
function pt(s, x, y, size, o = {}) {
  const a = o.alpha ?? 1; if (a <= 0) return;
  const font = `${o.w || 900} ${size}px ${FT.ui}`;
  ctx.save(); ctx.globalAlpha *= a; ctx.font = font; ctx.textAlign = o.a || 'center'; ctx.textBaseline = 'middle';
  if (o.shadow !== false) { ctx.fillStyle = '#1F1A24'; ctx.fillText(s, x + Math.round(size * .07), y + Math.round(size * .07)); }
  if (o.stroke) { ctx.lineJoin = 'round'; ctx.lineWidth = o.stroke; ctx.strokeStyle = '#1F1A24'; ctx.strokeText(s, x, y); }
  ctx.restore();
  txt(s, x, y, { font, color: o.c || '#FFFFFF', alpha: a, align: o.a || 'center', deco: o.deco });
}
function pixBox(x, y, w, h, a = 1, fill = '#2A2333') {
  if (a <= 0) return;
  ctx.save(); ctx.globalAlpha *= a;
  ctx.fillStyle = '#1F1A24'; ctx.fillRect(x - 8, y - 8, w + 16, h + 16);
  ctx.fillStyle = '#F4EEE2'; ctx.fillRect(x - 4, y - 4, w + 8, h + 8);
  ctx.fillStyle = fill; ctx.fillRect(x, y, w, h);
  ctx.restore();
  auditCover(x - 8, y - 8, w + 16, h + 16, .9 * a);
}
