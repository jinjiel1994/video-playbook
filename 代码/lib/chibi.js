// Q 版小人和小伙伴，各片共用（定妆图在 设计/Q版/）。画在全局的 ctx 上：片子里是 film.js 的 ctx，定妆图页面自己声明一个。
// chibi(x, y, h, o)：x, y 是两脚中间的落地点，h 是脚底到头顶的高（不算帽子尖、呆毛和头顶的符号）。o（都可以不给）：
//   who   预设的角色：'hero' 主角（少年冒险家：帽子、刺头、短外套、背包、短裤、大眼睛）；不给就是第一版的卫衣小人
//   view  'front' | 'side' | 'back'，side 朝右，flip: -1 朝左
//   pose  POSES 里的名字或一个对象；face FACES 里的名字或一个对象；sym 头顶符号 '?' '!' '…' '♥' 'vein' 'zz'
//   skin  'line' 描边扁平（默认，定了用这个）| 'paper' 剪纸 | 'pixel' 像素；age 'adult'（2.5 头身）| 'kid'（2 头身，小时候）
//   col   颜色，盖过 COL 里的同名项；hair 'short' | 'bun' | 'spiky'；hat 'cap'；outfit 'hoodie' | 'jacket'；pack 背包；
//   eyeStyle 'anime' 大眼睛带高光；glasses；fade 0–1 颜色褪成灰（麻木、空）；blink 0–1；bob 上半身往上提（呼吸）；
//   cow 呆毛 'up' | 'curl' | 'droop' | 'none'（默认跟表情走，戴帽子就没有）；a 透明度
// buddy(x, y, h, o)：小伙伴「问问」，h 是脚底到头顶（不算触角）。o.face 'calm' | 'happy' | 'puzzled' | 'surprised' | 'sad' | 'spark'，
//   o.antenna 盖过表情自带的触角（'up' | 'curl' 卷成问号 | 'droop' | 'spark' 亮一下），o.flip，o.a，o.lw 线宽（像素，默认和主角一样粗）。
// 比例（单位是身高的百分之一）：头 40%，身子 33%，腿 27%；头宽是肩宽的两倍；眼睛在头高的 58% 处，偏下显小；
// 手是圆的，比手腕粗；线宽是头高的 3.4%。改比例改 BODY，整片一套，不要一场一个样。
const CHIBI = (() => {
  const PI = Math.PI, TAU = PI * 2;
  const dv = th => [Math.sin(th), Math.cos(th)];   // th = 0 朝正下，正数转向 +x
  const hex = h => { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
  const toHex = ([r, g, b]) => '#' + ((1 << 24) + (Math.round(r) << 16) + (Math.round(g) << 8) + Math.round(b)).toString(16).slice(1);
  const mix = (a, b, p) => { const x = hex(a), y = hex(b); return toHex(x.map((v, i) => v + (y[i] - v) * p)); };
  const grey = (h, p) => { if (!p) return h; const [r, g, b] = hex(h), l = .3 * r + .59 * g + .11 * b; return mix(h, toHex([l, l, l]), p); };
  const hexA = (h, a) => { const [r, g, b] = hex(h); return `rgba(${r},${g},${b},${a})`; };

  const COL = { skin: '#ffdcc4', blush: '#ff9a8a', hair: '#2e2a33', top: '#f2a63a', topDk: '#d6851d', bottom: '#4b5a6e',
    shoe: '#f6f1e8', line: '#3a2e2a', white: '#ffffff', tear: '#7cc6f2', sym: '#e2574c', heart: '#ff6b81',
    tee: '#f7f3ea', cap: '#2f8c87', brim: '#24706c', badge: '#f2a63a', pack: '#b85a3e', iris: '#7a4a2c' };
  // 预设角色。主角（配色 C）：芥末黄短外套是他的颜色，奶白帽子配黄帽檐，袖口和领子也是深一点的黄，
  // 背包棕色；青绿只留给帽徽（往下的箭头，追到底）和小伙伴
  const WHO = {
    hero: { hat: 'cap', hair: 'spiky', outfit: 'jacket', pack: true, eyeStyle: 'anime',
      col: { top: '#f2a63a', topDk: '#e0922b', tee: '#f7f3ea', bottom: '#4b5a6e', hair: '#2b2630', cap: '#f4eee2', brim: '#e0922b', badge: '#2f8c87', pack: '#7a5236' } },
  };
  const BODY = {
    adult: { top: -98, chin: -60, rx: 21, ry: 19, tT: -63, tB: -24, tw: 21, bw: 26, sh: [9, -57], hip: [6, -27], leg: [13, 11], legR: [4.3, 3.5],
      arm: [11, 9.6], armR: [3, 2.5], hand: 3.2, foot: [5.2, 2.9], eye: [8.4, -75.6], eyeR: [2.4, 3.3], brow: -82, mouth: -67.6, blush: [13.6, -70.2] },
    kid: { top: -98, chin: -48, rx: 26, ry: 25, tT: -51, tB: -18, tw: 18, bw: 23, sh: [8, -46], hip: [5.4, -20], leg: [9.5, 8], legR: [3.8, 3.2],
      arm: [9, 8.2], armR: [2.7, 2.3], hand: 3, foot: [4.6, 2.6], eye: [10.4, -67], eyeR: [3.1, 4.3], brow: -76, mouth: -57, blush: [16.4, -59.5] },
  };

  // 姿势。正面：aL / aR / lL / lR = [往外张的角度, 肘或膝再往外弯的角度]，弧度；或 {to: [x, y]} 让手去够一个点（肘朝外）。
  // 侧面（side: true）：aN / aF 近处、远处的胳膊，lN / lF 近处、远处的腿，[角度, 弯]，正数朝前。
  // tilt 头歪，headDy 头往下沉，lean 整个人斜，dy 屁股往下坐，front 胳膊画在脸前面。
  const POSES = {
    stand: { aL: [.14, .05], aR: [.14, .05], lL: [.03, 0], lR: [.03, 0] },
    wave: { aL: [.14, .05], aR: [2.25, .65], tilt: -.07 },
    fist: { aL: { to: [-6.5, -49] }, aR: { to: [6.5, -49] }, lL: [.12, 0], lR: [.12, 0], front: true },   // 两只拳头收在胸前：加油
    point: { aL: { to: [-12.5, -42] }, aR: [1.5, .08], lL: [.1, 0], lR: [.08, 0] },
    chin: { aL: [.12, .25], aR: { to: [7.5, -63.5] }, tilt: .13, front: true },
    shrug: { aL: [.5, 1.45], aR: [.5, 1.45], tilt: .08 },
    cover: { aL: { to: [-8.5, -67.5] }, aR: { to: [8.5, -67.5] }, headDy: 1.2, front: true },
    hips: { aL: { to: [-13.5, -40] }, aR: { to: [13.5, -40] }, lL: [.1, 0], lR: [.1, 0] },
    slump: { aL: [.04, 0], aR: [.04, 0], headDy: 2.4, tilt: .1 },
    sideStand: { side: true, aN: [.06, -.12], aF: [-.06, -.1], lN: [.02, 0], lF: [-.02, 0] },
    walk: { side: true, aN: [-.5, -.3], aF: [.5, -.45], lN: [.42, -.08], lF: [-.38, .45], bob: .6 },
    run: { side: true, lean: .1, aN: [-.95, 2.1], aF: [.85, 1.5], lN: [1.05, -1.5], lF: [-.55, -.95], bob: 3 },
    sit: { side: true, aN: [.42, -1.0], aF: [.32, -.9], lN: [PI / 2, -PI / 2], lF: [1.48, -1.48], dy: 13 },
  };

  // 表情：eyes / brows（[内侧抬起的角度, 上下]，左右各一）/ mouth / blush 腮红深浅 / tears / sweat / cow 呆毛
  const FACES = {
    calm: { eyes: 'dot', brows: [[0, 0], [0, 0]], mouth: 'smile', blush: .8, cow: 'up' },
    determined: { eyes: 'dot', brows: [[-.32, .2], [-.32, .2]], mouth: 'smirk', blush: .8, cow: 'up' },
    happy: { eyes: 'happy', brows: [[.1, -1], [.1, -1]], mouth: 'grin', blush: 1.2, cow: 'up' },
    sad: { eyes: 'dot', brows: [[.45, 0], [.45, 0]], mouth: 'frown', blush: .6, tears: 1, cow: 'droop' },
    cry: { eyes: 'tight', brows: [[.5, 0], [.5, 0]], mouth: 'wail', blush: 1, tears: 2, cow: 'droop' },
    angry: { eyes: 'dot', brows: [[-.5, .6], [-.5, .6]], mouth: 'shout', blush: 1, cow: 'up', sym: 'vein' },
    hold: { eyes: 'flat', brows: [[.3, 0], [.3, 0]], mouth: 'wavy', blush: .6, sweat: 1, cow: 'droop', sym: '…' },
    puzzled: { eyes: 'dot', brows: [[.05, -1.6], [-.2, .3]], mouth: 'o', blush: .6, cow: 'curl', sym: '?' },
    surprised: { eyes: 'wide', brows: [[0, -2], [0, -2]], mouth: 'O', blush: .6, cow: 'up', sym: '!' },
    tender: { eyes: 'soft', brows: [[.12, -.5], [.12, -.5]], mouth: 'smile', blush: 1.5, cow: 'up', sym: '♥' },
    blank: { eyes: 'hollow', brows: null, mouth: 'flat', blush: 0, cow: 'none', fade: .65 },
    think: { eyes: 'dot', brows: [[.1, -.8], [-.1, 0]], mouth: 'side', blush: .6, cow: 'curl' },
  };

  let c, K, B, SK, FACE, O;   // 当前画布、颜色、身体比例、画法、表情、选项
  let LW = 1.3, FW = 1;       // 描边粗细、五官线条的倍数（都是当前单位）
  let ES = 1, BD = 0;         // 眼睛放大、眉毛上移（大眼睛的角色）

  // ---------- 形状：都只往当前路径里加一段，由 G() 统一描边和上色 ----------
  function cap(ax, ay, bx, by, r1, r2) {
    const a = Math.atan2(by - ay, bx - ax);
    c.moveTo(ax + Math.cos(a + PI / 2) * r1, ay + Math.sin(a + PI / 2) * r1);
    c.arc(ax, ay, r1, a + PI / 2, a + PI * 1.5);
    c.lineTo(bx + Math.cos(a - PI / 2) * r2, by + Math.sin(a - PI / 2) * r2);
    c.arc(bx, by, r2, a - PI / 2, a + PI / 2);
    c.closePath();
  }
  function ell(x, y, rx, ry, rot = 0) { c.moveTo(x + rx * Math.cos(rot), y + rx * Math.sin(rot)); c.ellipse(x, y, rx, ry, rot, 0, TAU); c.closePath(); }
  function rtrap(cx, y1, y2, wT, wB, rT, rB) {
    c.moveTo(cx, y1); c.arcTo(cx + wT / 2, y1, cx + wB / 2, y2, rT); c.arcTo(cx + wB / 2, y2, cx, y2, rB);
    c.arcTo(cx - wB / 2, y2, cx - wT / 2, y1, rB); c.arcTo(cx - wT / 2, y1, cx, y1, rT); c.closePath();
  }
  function polyP(pts) { pts.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.closePath(); }
  // 一组形状：描边扁平是先用两倍线宽描一圈深色，再整组填色，组里互相压住的地方不留线；剪纸是先错开一点填一层影子
  function G(fill, build) {
    if (SK === 'paper') {
      c.save(); c.translate(.6, .9); c.beginPath(); build(); c.fillStyle = 'rgba(40,24,16,.22)'; c.fill(); c.restore();
      c.beginPath(); build(); c.fillStyle = fill; c.fill(); return;
    }
    c.beginPath(); build(); c.lineJoin = 'round'; c.lineWidth = LW * 2; c.strokeStyle = K.line; c.stroke(); c.fillStyle = fill; c.fill();
  }
  // 五官和符号的线：剪纸里也用深色
  function stroke(w, col, build) { c.beginPath(); build(); c.lineCap = 'round'; c.lineJoin = 'round'; c.lineWidth = w * FW; c.strokeStyle = col || K.line; c.stroke(); }
  function fill(col, build) { c.beginPath(); build(); c.fillStyle = col; c.fill(); }

  function ik(S, T, L1, L2, side) {
    const dx = T[0] - S[0], dy = T[1] - S[1];
    const d = Math.min(Math.max(Math.hypot(dx, dy), Math.abs(L1 - L2) + .01), L1 + L2 - .01);
    const base = Math.atan2(dy, dx), a = Math.acos((L1 * L1 + d * d - L2 * L2) / (2 * L1 * d));
    const e1 = [S[0] + Math.cos(base + a) * L1, S[1] + Math.sin(base + a) * L1], e2 = [S[0] + Math.cos(base - a) * L1, S[1] + Math.sin(base - a) * L1];
    const E = e1[0] * side > e2[0] * side ? e1 : e2, ang = Math.atan2(T[1] - E[1], T[0] - E[0]);
    return { E, W: [E[0] + Math.cos(ang) * (L2 - 1.3), E[1] + Math.sin(ang) * (L2 - 1.3)], H: [E[0] + Math.cos(ang) * L2, E[1] + Math.sin(ang) * L2] };
  }
  function armPts(S, spec, side) {
    const [L1, L2] = B.arm;
    if (spec && spec.to) return ik(S, spec.to, L1, L2 + 1.3, side);
    const [o, b] = spec || [.14, .05], t1 = side * o, t2 = side * (o + b);
    const [d1x, d1y] = dv(t1), [d2x, d2y] = dv(t2);
    const E = [S[0] + d1x * L1, S[1] + d1y * L1], W = [E[0] + d2x * L2, E[1] + d2y * L2];
    return { E, W, H: [W[0] + d2x * 1.3, W[1] + d2y * 1.3] };
  }
  function legPts(Hp, spec, side) {
    const [L1, L2] = B.leg, [o, b] = spec || [.03, 0], t1 = side * o, t2 = side * (o + b);
    const [d1x, d1y] = dv(t1), [d2x, d2y] = dv(t2);
    const Kn = [Hp[0] + d1x * L1, Hp[1] + d1y * L1];
    return { K: Kn, A: [Kn[0] + d2x * L2, Kn[1] + d2y * L2], t2 };
  }
  const along = (P, Q, t) => [P[0] + (Q[0] - P[0]) * t, P[1] + (Q[1] - P[1]) * t];
  // 胳膊：卫衣是长袖；短外套是短袖（袖口一圈青绿），小臂露出来
  function drawArms(list, sleeve, cuff, skin) {
    if (O.outfit === 'jacket') {
      G(skin, () => list.forEach(([, p]) => { cap(p.E[0], p.E[1], p.W[0], p.W[1], B.armR[0] * .8, B.armR[1] * .88); ell(p.H[0], p.H[1], B.hand, B.hand); }));
      G(sleeve, () => list.forEach(([S, p]) => { const e = along(S, p.E, .86); cap(S[0], S[1], e[0], e[1], B.armR[0] * 1.08, B.armR[0] * 1.08); }));
      G(cuff, () => list.forEach(([S, p]) => { const a = along(S, p.E, .7), e = along(S, p.E, .86); cap(a[0], a[1], e[0], e[1], B.armR[0] * 1.1, B.armR[0] * 1.1); }));
      return;
    }
    G(sleeve, () => list.forEach(([S, p]) => { cap(S[0], S[1], p.E[0], p.E[1], B.armR[0], B.armR[0] * .92); cap(p.E[0], p.E[1], p.W[0], p.W[1], B.armR[0] * .92, B.armR[1]); }));
    G(skin, () => list.forEach(([, p]) => ell(p.H[0], p.H[1], B.hand, B.hand)));
  }
  // 腿：卫衣配长裤；短外套配短裤，小腿露出来
  function drawLegs(list, trouser, shoe, skin, sideView) {
    if (O.outfit === 'jacket') {
      G(skin, () => list.forEach(([, p]) => cap(p.K[0], p.K[1], p.A[0], p.A[1], B.legR[0] * .76, B.legR[1] * .92)));
      G(trouser, () => list.forEach(([Hp, p]) => { const k = along(Hp, p.K, 1.06); cap(Hp[0], Hp[1], k[0], k[1], B.legR[0] * 1.12, B.legR[0] * 1.08); }));
    } else G(trouser, () => list.forEach(([Hp, p]) => { cap(Hp[0], Hp[1], p.K[0], p.K[1], B.legR[0], B.legR[0] * .9); cap(p.K[0], p.K[1], p.A[0], p.A[1], B.legR[0] * .9, B.legR[1]); }));
    G(shoe, () => list.forEach(([, p, side]) => {
      if (sideView) ell(p.A[0] + 2.3, p.A[1] + .5, B.foot[0] * 1.1, B.foot[1], Math.max(-.5, Math.min(.5, -p.t2 * .6)));
      else ell(p.A[0] + side * 1.2, p.A[1] + .5, B.foot[0], B.foot[1], side * .08);
    }));
  }

  // ---------- 头 ----------
  const cy = () => (B.top + B.chin) / 2;
  function hairFront() {
    const y0 = cy() - .6, R = B.rx + 1.6, Ry = B.ry + 1.5, ey = B.eye[1], k = B.rx / 21;
    const aL = PI - Math.asin(Math.min(.9, (ey + 1.6 - y0) / Ry)), aR = TAU + Math.asin(Math.min(.9, (ey - 1.2 - y0) / Ry));
    c.moveTo(R * Math.cos(aL), y0 + Ry * Math.sin(aL));
    c.ellipse(0, y0, R, Ry, 0, aL, aR);
    c.quadraticCurveTo(B.rx - 1.2, ey - 4, B.rx - 3.2, B.brow - 2.2);                       // 右边鬓角往里收
    const f = [[B.rx - 3.2, B.brow - 2.2], [9 * k, B.brow - 3.8], [.5 * k, B.brow - 2.9], [-8.6 * k, B.brow - 1.3], [-B.rx + 4, B.brow + .4]];
    for (let i = 0; i < f.length - 1; i++) c.quadraticCurveTo((f[i][0] + f[i + 1][0]) / 2, Math.max(f[i][1], f[i + 1][1]) + 3.4, f[i + 1][0], f[i + 1][1]);
    c.quadraticCurveTo(-B.rx + 1.6, ey - 2.5, R * Math.cos(aL) + 2.4, y0 + Ry * Math.sin(aL));   // 左边鬓角
    c.closePath();
  }
  function hairSide() {
    const y0 = cy() - .6, R = B.rx + 1.5, Ry = B.ry + 1.5;
    c.moveTo(-.8 + R * Math.cos(-.62), y0 + Ry * Math.sin(-.62));
    c.ellipse(-.8, y0, R, Ry, 0, -.62, PI * .74, true);
    c.quadraticCurveTo(-B.rx * .55, B.chin - 2, -B.rx * .2, B.eye[1] + 1.5);
    c.quadraticCurveTo(B.rx * .05, B.brow - 4, B.rx * .25, B.brow - 2.4);
    c.quadraticCurveTo(B.rx * .45, B.brow + 1, B.rx * .58, B.brow - 2.6);
    c.quadraticCurveTo(B.rx * .72, B.brow + .6, B.rx * .84, B.brow - 2.8);
    c.closePath();
  }
  function hairBack() {
    const y0 = cy() - .6, R = B.rx + 1.6, Ry = B.ry + 1.5;
    c.moveTo(R, y0); c.ellipse(0, y0, R, Ry, 0, 0, PI, true);
    const ny = B.chin - 3.2, xs = [-R * .78, -R * .4, 0, R * .4, R * .78];
    c.quadraticCurveTo(-R * .98, ny - 2, xs[0], ny);
    for (let i = 0; i < xs.length - 1; i++) c.quadraticCurveTo((xs[i] + xs[i + 1]) / 2, ny + 3, xs[i + 1], ny);
    c.quadraticCurveTo(R * .98, ny - 2, R, y0);
    c.closePath();
  }
  // 刺头：帽檐下面两边各支出三撮
  const capY = () => B.brow + BD - 6.5;   // 帽子下沿
  function spikes(s) {
    const R = B.rx, y = capY(), k = B.ry / 19;
    polyP([[s * (R - 4), y - 1], [s * (R + 4.2), y + 1 * k], [s * (R + .3), y + 4 * k], [s * (R + 3.6), y + 7.8 * k], [s * (R - .2), y + 9.6 * k],
      [s * (R + 1.8), y + 13.4 * k], [s * (R - 2.8), y + 12.4 * k], [s * (R - 5), y + 5 * k]]);
  }
  function spikesBack() {   // 侧面：脑后支出来
    const R = B.rx + 1.5, y = capY() + 1, k = B.ry / 19;
    polyP([[-R + 4, y - 1], [-R - 4.5, y + 1.5 * k], [-R - .5, y + 4.6 * k], [-R - 4, y + 8.5 * k], [-R + .5, y + 10 * k], [-R - 2, y + 14 * k], [-R + 4, y + 12 * k]]);
  }
  function capFront() {
    const R = B.rx + 2, eb = capY(), top = B.top - 8.5, pk = (2 * eb + 6 * top) / 8;   // pk 帽顶
    G(K.cap, () => { c.moveTo(-R, eb); c.bezierCurveTo(-R, top, R, top, R, eb); c.quadraticCurveTo(0, eb + 2.4, -R, eb); c.closePath(); });
    if (SK !== 'paper') stroke(.75, K.line, () => { c.moveTo(0, pk + .4); c.quadraticCurveTo(-7, eb - 7, -8.5, eb + 1.2); c.moveTo(0, pk + .4); c.quadraticCurveTo(7, eb - 7, 8.5, eb + 1.2); });
    G(K.cap, () => ell(0, pk, 1.7, 1.2));
    G(K.brim, () => {
      c.moveTo(-R * .84, eb + .2); c.quadraticCurveTo(0, eb + 2.6, R * .84, eb + .2);
      c.quadraticCurveTo(R * .92, eb + 3.2, R * .6, eb + 4.3); c.quadraticCurveTo(0, eb + 6.6, -R * .6, eb + 4.3);
      c.quadraticCurveTo(-R * .92, eb + 3.2, -R * .84, eb + .2); c.closePath();
    });
    G(K.white, () => ell(0, eb - 4.6, 3.5, 3.3));   // 帽徽：往下的箭头
    stroke(1.3, K.badge, () => { c.moveTo(0, eb - 7); c.lineTo(0, eb - 2.6); c.moveTo(-1.9, eb - 4.4); c.lineTo(0, eb - 2.4); c.lineTo(1.9, eb - 4.4); });
  }
  function capSide() {
    const R = B.rx + 1.8, eb = capY(), top = B.top - 9.5;
    G(K.cap, () => { c.moveTo(-R * .98, eb + 2); c.bezierCurveTo(-R * 1.05, top, R * .85, top - 1, R * .88, eb); c.quadraticCurveTo(0, eb + 3.2, -R * .98, eb + 2); c.closePath(); });
    G(K.cap, () => ell(-R * .08, (2 * eb + 6 * top) / 8 - .3, 1.6, 1.1));
    G(K.brim, () => { c.moveTo(R * .5, eb - .2); c.quadraticCurveTo(R * 1.3, eb - 1.4, R * 1.5, eb + 1.8); c.quadraticCurveTo(R * 1.05, eb + 3.2, R * .45, eb + 2.6); c.closePath(); });
    G(K.white, () => ell(R * .46, eb - 4.6, 2.4, 3)); stroke(1.1, K.badge, () => { c.moveTo(R * .46, eb - 6.6); c.lineTo(R * .46, eb - 3); });
  }
  function capBack() {
    const R = B.rx + 2, eb = capY() + 1, top = B.top - 8.5;
    G(K.cap, () => { c.moveTo(-R, eb); c.bezierCurveTo(-R, top, R, top, R, eb); c.quadraticCurveTo(0, eb + 2.4, -R, eb); c.closePath(); });
    G(K.cap, () => ell(0, (2 * eb + 6 * top) / 8, 1.7, 1.2));
    G(K.hair, () => { c.moveTo(-4.2, eb + 1.6); c.arc(0, eb + 1.6, 4.2, PI, 0); c.closePath(); });   // 后面调节扣的口
    G(K.brim, () => rtrap(0, eb - .4, eb + 1.8, 9.5, 9.5, 1, 1));
  }
  function cowlick(state, side) {
    if (state === 'none' || O.hat) return;
    const x = side ? -1 : 2, y = B.top - .3;
    const path = () => {
      c.moveTo(x, y);
      if (state === 'up') c.bezierCurveTo(x - 1.5, y - 4, x + 1, y - 7.5, x + 5, y - 8);
      else if (state === 'curl') c.bezierCurveTo(x - 2.5, y - 6, x + 4.5, y - 10.5, x + 6.2, y - 6.5), c.bezierCurveTo(x + 7, y - 4.5, x + 4.2, y - 3.6, x + 3.4, y - 5.6);
      else c.bezierCurveTo(x + 1.5, y - 6.5, x + 7, y - 7, x + 9.5, y - 1.8);   // droop
    };
    if (SK !== 'paper') stroke((1.9 + LW * 2) / FW, K.line, path);
    stroke(1.9 / FW, K.hair, path);
  }

  function eye(x, y, type) {
    const rx = B.eyeR[0] * ES, ry = B.eyeR[1] * ES, blink = FACE.blink || 0;
    if (type === 'anime') {
      const ax = rx * 1.05, ay = ry * 1.05 * (1 - blink * .92);
      if (blink > .75) { stroke(1.2, K.line, () => { c.moveTo(x - ax, y); c.quadraticCurveTo(x, y + 1.2, x + ax, y); }); return; }
      fill(K.line, () => ell(x, y, ax, ay));
      c.save(); c.beginPath(); ell(x, y, ax, ay); c.clip(); fill(K.iris, () => ell(x, y + ay * .38, ax * .78, ay * .72)); c.restore();
      fill(K.white, () => ell(x + ax * .3, y - ay * .38, ax * .4, ax * .4));
      fill(K.white, () => ell(x - ax * .34, y + ay * .46, ax * .17, ax * .17));
    } else if (type === 'dot') {
      const h = ry * (1 - blink * .9);
      fill(K.line, () => ell(x, y, rx, h));
      if (blink < .5) fill(K.white, () => ell(x + rx * .35, y - h * .38, rx * .36, rx * .36));
    } else if (type === 'happy') stroke(1.15, K.line, () => c.arc(x, y + 1.2 * ES, rx * 1.15, PI * 1.12, PI * 1.88));
    else if (type === 'soft') stroke(1.15, K.line, () => c.arc(x, y - 1 * ES, rx * 1.1, PI * .14, PI * .86));
    else if (type === 'flat') stroke(1.2, K.line, () => { c.moveTo(x - rx * 1.1, y); c.lineTo(x + rx * 1.1, y); });
    else if (type === 'tight') { const d = x > 0 ? -1 : 1; stroke(1.15, K.line, () => { c.moveTo(x - d * rx * 1.1, y - ry * .6); c.lineTo(x + d * rx * .8, y); c.lineTo(x - d * rx * 1.1, y + ry * .6); }); }
    else if (type === 'wide') {
      fill(K.white, () => ell(x, y, rx * 1.45, ry * 1.25)); stroke(.9, K.line, () => ell(x, y, rx * 1.45, ry * 1.25));
      fill(K.line, () => ell(x, y + .3, rx * .7, ry * .62)); fill(K.white, () => ell(x + rx * .3, y - ry * .2, rx * .26, rx * .26));
    } else if (type === 'hollow') stroke(.85, K.line, () => ell(x, y, rx * 1.05, ry * .95));
  }
  function brow(x, by, spec, inner) {   // inner = 内侧朝哪边（+1 朝右）
    if (!spec) return;
    const [ang, dy] = spec, L = 2.5 * (B.eyeR[0] / 2.4) * (ES > 1 ? 1.15 : 1), s = Math.sin(ang) * L;
    stroke(ES > 1 ? 1.55 : 1.05, K.line, () => { c.moveTo(x - inner * L, by + BD + dy + s); c.lineTo(x + inner * L, by + BD + dy - s); });
  }
  function mouth(x, y, type, s = 1) {
    const w = 2.6 * s * (B.rx / 21);
    if (type === 'smile') stroke(1.05, K.line, () => c.arc(x, y - w * .7, w, PI * .2, PI * .8));
    else if (type === 'smirk') stroke(1.1, K.line, () => { c.moveTo(x - w * .9, y - .3); c.quadraticCurveTo(x + w * .1, y + 1.5, x + w * 1.1, y - 1.2); });
    else if (type === 'frown') stroke(1.05, K.line, () => c.arc(x, y + w * .8, w * .9, PI * 1.22, PI * 1.78));
    else if (type === 'flat') stroke(1.05, K.line, () => { c.moveTo(x - w * .7, y); c.lineTo(x + w * .7, y); });
    else if (type === 'side') stroke(1.05, K.line, () => { c.moveTo(x - w * .3, y + .2); c.quadraticCurveTo(x + w * .4, y + .1, x + w * .9, y - .7); });
    else if (type === 'wavy') stroke(1, K.line, () => { c.moveTo(x - w * 1.1, y); for (let i = 1; i <= 4; i++) c.lineTo(x - w * 1.1 + i * w * .55, y + (i % 2 ? .75 : -.1)); });
    else if (type === 'o') fill(K.line, () => ell(x + .6, y, w * .45, w * .55));
    else if (type === 'w') stroke(1.05, K.line, () => { c.arc(x - w * .45, y - .4, w * .45, PI * .1, PI * .95); c.moveTo(x + w * .9, y - .2); c.arc(x + w * .45, y - .4, w * .45, PI * .05, PI * .9); });
    else if (type === 'O') { fill(K.line, () => ell(x, y + .6, w * .8, w * 1.05)); fill('#e8747c', () => ell(x, y + 1.6, w * .5, w * .35)); }
    else if (type === 'grin' || type === 'shout' || type === 'wail') {
      const top = y - .9, ww = type === 'grin' ? w * 1.35 : w * 1.25, hh = type === 'wail' ? w * 1.2 : w * 1.3;
      fill(K.line, () => {
        if (type === 'shout') { c.moveTo(x - ww, top); c.lineTo(x + ww, top); c.lineTo(x + ww * .62, top + hh * 1.3); c.lineTo(x - ww * .62, top + hh * 1.3); c.closePath(); }
        else if (type === 'wail') { c.moveTo(x - ww, top + hh); c.quadraticCurveTo(x, top - hh * .6, x + ww, top + hh); c.quadraticCurveTo(x, top + hh * 1.5, x - ww, top + hh); c.closePath(); }
        else { c.moveTo(x - ww, top); c.lineTo(x + ww, top); c.ellipse(x, top, ww, hh, 0, 0, PI); c.closePath(); }
      });
      fill('#e8747c', () => ell(x, top + (type === 'wail' ? hh * 1.15 : hh * .78), ww * .5, hh * .3));
    }
  }
  function tearDrop(x, y, r) {
    G(K.tear, () => { c.moveTo(x, y - r * 1.9); c.quadraticCurveTo(x + r * 1.1, y - r * .3, x + r, y + .1); c.arc(x, y, r, 0, PI); c.quadraticCurveTo(x - r * 1.1, y - r * .3, x, y - r * 1.9); c.closePath(); });
  }
  const eyeType = t => ES > 1 && t === 'dot' ? 'anime' : t;
  function face(view, f) {
    const ey = B.eye[1], ex = B.eye[0];
    if (view === 'side') {
      const x = B.rx * .5;
      if (f.blush) fill(hexA(K.blush, .5 * f.blush), () => ell(x - 2.6, B.blush[1], 3, 1.7));
      eye(x, ey, eyeType(f.eyes)); if (f.brows) brow(x, B.brow, f.brows[1], 1);
      mouth(B.rx * .76, B.mouth, f.mouth, .8);
      if (f.tears === 1) tearDrop(x - .6, ey + 5, 1.2);
      if (f.tears === 2) fill(hexA(K.tear, .9), () => { c.moveTo(x - 2, ey + 2); c.lineTo(x, ey + 2); c.lineTo(x - .6, B.chin + 1); c.lineTo(x - 2.4, B.chin + 1); c.closePath(); });
      return;
    }
    if (f.blush) [-1, 1].forEach(s => fill(hexA(K.blush, .5 * f.blush), () => ell(s * B.blush[0], B.blush[1] + (ES > 1 ? 1 : 0), 3.4 * B.rx / 21, 1.9 * B.rx / 21)));
    [-1, 1].forEach(s => eye(s * ex, ey, eyeType(f.eyes)));
    if (f.brows) { brow(-ex, B.brow, f.brows[0], 1); brow(ex, B.brow, f.brows[1], -1); }
    if (f.tears === 2) [-1, 1].forEach(s => fill(hexA(K.tear, .9), () => { const x = s * ex; c.moveTo(x - 1.4, ey + 2); c.lineTo(x + 1.4, ey + 2); c.lineTo(x + 1.8 * s * .4 + 1, B.chin + .5); c.lineTo(x + 1.8 * s * .4 - 1.6, B.chin + .5); c.closePath(); }));
    mouth(0, B.mouth, f.mouth);
    if (f.tears === 1) tearDrop(-ex - .4, ey + 5.2 * ES, 1.25);
    if (f.sweat) tearDrop(B.rx - 3.5, B.brow - 4.5 + (O.hat ? 3 : 0), 1.7);
  }

  function symbol(s, x, y) {
    if (!s) return;
    if (s === '…') { [0, 1, 2].forEach(i => G(K.line, () => ell(x + i * 3.6, y + 2, 1.15, 1.15))); return; }
    if (s === '♥') { G(K.heart, () => { c.moveTo(x, y + 4.2); c.bezierCurveTo(x - 6.5, y - .5, x - 3, y - 5.5, x, y - 2.2); c.bezierCurveTo(x + 3, y - 5.5, x + 6.5, y - .5, x, y + 4.2); c.closePath(); }); return; }
    if (s === 'vein') { [[1, 1], [-1, 1], [1, -1], [-1, -1]].forEach(([sx, sy]) => stroke(1.35, K.sym, () => { c.moveTo(x + sx * 1, y + sy * 3.2); c.quadraticCurveTo(x + sx * 1.2, y + sy * 1.2, x + sx * 3.2, y + sy * 1); })); return; }
    const t = s === 'zz' ? 'z' : s;
    c.save(); c.font = `900 ${s === 'zz' ? 8 : 12}px "Source Han Sans CN", "PingFang SC", sans-serif`; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.lineJoin = 'round'; if (SK !== 'paper') { c.lineWidth = LW * 2; c.strokeStyle = K.line; c.strokeText(t, x, y); }
    c.fillStyle = s === 'zz' ? K.line : K.sym; c.fillText(t, x, y); c.restore();
  }

  // ---------- 身子 ----------
  function torsoFront(back) {
    if (O.outfit !== 'jacket') {
      if (!back) G(K.topDk, () => rtrap(0, B.tT - 1.6, B.tT + 4.2, B.tw * 1.05, B.tw * .92, 3, 2.5));   // 帽兜堆在脖子后面
      G(K.top, () => rtrap(0, B.tT, B.tB, B.tw, B.bw, 6, 4));
      if (back) { G(K.topDk, () => rtrap(0, B.tT - 1, B.tT + 12, B.tw * .95, B.tw * .62, 4, 6)); return; }
      if (SK === 'paper') { fill(K.topDk, () => rtrap(0, B.tB - 11, B.tB - 3.5, B.bw * .5, B.bw * .62, 2.5, 1.5)); return; }
      stroke(.85, K.line, () => rtrap(0, B.tB - 11, B.tB - 3.5, B.bw * .5, B.bw * .62, 2.5, 1.5));
      [-1, 1].forEach(s => { stroke(.8, K.line, () => { c.moveTo(s * 3, B.tT + 3.5); c.lineTo(s * 3.3, B.tT + 9.5); }); G(K.shoe, () => ell(s * 3.3, B.tT + 10.4, .9, .9)); });
      return;
    }
    // 短外套：里面一件浅色 T 恤，外套敞开，领子翻起来
    if (!back) G(K.topDk, () => rtrap(0, B.tT - 1.8, B.tT + 3.6, B.tw * 1.02, B.tw * .9, 3, 2.5));
    if (back) { G(K.top, () => rtrap(0, B.tT, B.tB, B.tw, B.bw, 6, 4)); return; }
    G(K.tee, () => rtrap(0, B.tT, B.tB, B.tw, B.bw, 6, 4));
    c.save(); c.beginPath(); rtrap(0, B.tT, B.tB, B.tw, B.bw, 6, 4); c.clip();
    const k = B.tw / 21;
    G(K.top, () => { [-1, 1].forEach(s => polyP([[s * 2.4 * k, B.tT - 3], [s * 16, B.tT - 3], [s * 18, B.tB + 3], [s * 5.4 * k, B.tB + 3]])); });
    G(K.topDk, () => { [-1, 1].forEach(s => polyP([[s * 2.4 * k, B.tT - 1], [s * 7.4 * k, B.tT - 1], [s * 4 * k, B.tT + 6.5 * k]])); });   // 翻领
    c.restore();
    if (O.pack) G(K.pack, () => [-1, 1].forEach(s => cap(s * 6.6 * k, B.tT + .5, s * 8.8 * k, B.tT + 17, 1.5, 1.4)));   // 背包带
  }
  function packBack() { G(K.pack, () => rtrap(0, B.tT + 3, B.tT + 28, B.tw * .82, B.tw * .92, 5, 5)); G(mix(K.pack, K.line, .14), () => rtrap(0, B.tT + 3, B.tT + 12, B.tw * .82, B.tw * .86, 5, 3)); G(K.badge, () => ell(0, B.tT + 12, 1.4, 1.4)); }

  // ---------- 整个人 ----------
  function body(o) {
    const view = o.view || 'front', pz = typeof o.pose === 'string' ? POSES[o.pose] : (o.pose || (view === 'side' ? POSES.sideStand : POSES.stand));
    const f = { ...(typeof o.face === 'string' ? FACES[o.face] : (o.face || FACES.calm)) }; f.blink = o.blink || 0; FACE = f;
    const dy = pz.dy || 0, bob = (o.bob || 0) + (pz.bob || 0);
    const far = col => mix(col, K.line, .16), cuff = K.topDk;
    c.save(); c.rotate(pz.lean || 0);
    const up = (fn) => { c.save(); c.translate(0, dy - bob); fn(); c.restore(); };   // 上半身（随坐下、呼吸移动）
    const headT = (fn) => { c.save(); c.translate(0, dy - bob + (pz.headDy || 0)); c.translate(0, B.tT); c.rotate(pz.tilt || 0); c.translate(0, -B.tT); fn(); c.restore(); };
    const spiky = o.hair === 'spiky';

    if (view === 'side') {
      const Hp = [.3, B.hip[1] + dy - bob * .4], S = [.4, B.sh[1] + dy - bob];
      const lN = legPts(Hp, pz.lN, 1), lF = legPts([Hp[0] - .6, Hp[1]], pz.lF, 1);
      const aN = armPts(S, pz.aN, 1), aF = armPts([S[0] - .8, S[1]], pz.aF, 1);
      drawArms([[[S[0] - .8, S[1]], aF]], far(K.top), far(cuff), far(K.skin));
      drawLegs([[[Hp[0] - .6, Hp[1]], lF, 1]], far(K.bottom), far(K.shoe), far(K.skin), true);
      drawLegs([[Hp, lN, 1]], K.bottom, K.shoe, K.skin, true);
      up(() => {
        if (o.pack) G(K.pack, () => rtrap(-B.tw * .39 - 3.2, B.tT + 2, B.tT + 26, 8, 9, 3.5, 3.5));
        G(K.topDk, () => ell(-6.5, B.tT + 2.2, 5.6, 3.6));
        G(K.top, () => rtrap(.3, B.tT, B.tB, B.tw * .78, B.bw * .76, 5.5, 3.5));
        if (o.outfit === 'jacket') {
          c.save(); c.beginPath(); rtrap(.3, B.tT, B.tB, B.tw * .78, B.bw * .76, 5.5, 3.5); c.clip();
          G(K.tee, () => polyP([[B.tw * .3, B.tT - 2], [B.tw * .6, B.tT - 2], [B.bw * .6, B.tB + 2], [B.bw * .3, B.tB + 2]]));
          G(K.topDk, () => rtrap(0, B.tB - 3, B.tB + 2, B.bw + 2, B.bw + 2, 0, 0)); c.restore();
          if (o.pack) G(K.pack, () => cap(-2.6, B.tT + .5, .8, B.tT + 14, 1.5, 1.4));
        } else if (SK !== 'paper') stroke(.85, K.line, () => { c.moveTo(B.bw * .2, B.tB - 9); c.quadraticCurveTo(B.bw * .1, B.tB - 4, B.bw * .32, B.tB - 1.5); });
      });
      headT(() => {
        if (o.hair === 'bun') G(K.hair, () => ell(-B.rx * .55, B.top + 3, 6.2, 6.2));
        if (spiky) G(K.hair, spikesBack);
        G(K.skin, () => ell(0, cy(), B.rx * .97, B.ry));
        G(K.hair, hairSide);
        G(K.skin, () => ell(-B.rx * .12, B.eye[1] + 1, 2.4, 3));
        if (o.hat === 'cap') capSide();
        face('side', f); cowlick(o.cow || f.cow, true);
        if (o.glasses) stroke(.9, K.line, () => { ell(B.rx * .5, B.eye[1], 4, 3.8); c.moveTo(B.rx * .5 - 4, B.eye[1]); c.lineTo(-B.rx * .1, B.eye[1] - .5); });
      });
      drawArms([[S, aN]], K.top, cuff, K.skin);
      c.restore(); return { top: B.top + dy };
    }

    const back = view === 'back';
    const Hl = [-B.hip[0], B.hip[1] + dy], Hr = [B.hip[0], B.hip[1] + dy];
    const Sl = [-B.sh[0], B.sh[1] + dy - bob], Sr = [B.sh[0], B.sh[1] + dy - bob];
    const aL = armPts(Sl, pz.aL, -1), aR = armPts(Sr, pz.aR, 1);
    drawLegs([[Hl, legPts(Hl, pz.lL, -1), -1], [Hr, legPts(Hr, pz.lR, 1), 1]], K.bottom, K.shoe, K.skin, false);
    up(() => { if (o.pack && !back) G(K.pack, () => [-1, 1].forEach(s => rtrap(s * (B.tw / 2 + 1.2), B.tT + 4, B.tT + 22, 4, 4.4, 2, 2))); torsoFront(back); if (back && o.pack) packBack(); });
    if (!pz.front) drawArms([[Sl, aL], [Sr, aR]], K.top, cuff, K.skin);
    headT(() => {
      if (o.hair === 'bun') G(K.hair, () => ell(0, B.top - 1, 6.6, 6.3));
      G(K.skin, () => { ell(-B.rx + .4, B.eye[1] + 1.5, 2.6, 3.1); ell(B.rx - .4, B.eye[1] + 1.5, 2.6, 3.1); });
      G(K.skin, () => ell(0, cy(), B.rx, B.ry));
      if (back) { G(K.hair, hairBack); if (spiky) G(K.hair, () => { spikes(-1); spikes(1); }); if (o.hat === 'cap') capBack(); cowlick(o.cow || f.cow, false); return; }
      if (spiky) { G(K.hair, () => { spikes(-1); spikes(1); }); G(K.hair, hairFrontCap); }
      else G(K.hair, hairFront);
      if (o.hat === 'cap') capFront();
      face('front', f); cowlick(o.cow || f.cow, false);
      if (o.glasses) stroke(.9, K.line, () => { [-1, 1].forEach(s => ell(s * B.eye[0], B.eye[1], 4.3, 4)); c.moveTo(-B.eye[0] + 4.3, B.eye[1] - .5); c.lineTo(B.eye[0] - 4.3, B.eye[1] - .5); });
    });
    if (pz.front) drawArms([[Sl, aL], [Sr, aR]], K.top, cuff, K.skin);
    c.restore();
    return { top: B.top + dy };
  }
  // 戴帽子时帽檐下露出的一排刘海尖
  function hairFrontCap() {
    const y = capY() + 3.4, R = B.rx - 1.5, n = 7, k = B.ry / 19;
    c.moveTo(-R, y - 3);
    for (let i = 0; i <= n; i++) { const x = -R + (2 * R) * i / n; c.lineTo(x, y - 3); if (i < n) c.lineTo(x + R / n, y + (i % 2 ? 2.6 : 3.6) * k); }
    c.lineTo(R, y - 3); c.closePath();
  }

  let NOISE = null;
  function noise() {
    if (NOISE) return NOISE;
    NOISE = document.createElement('canvas'); NOISE.width = NOISE.height = 256;
    const g = NOISE.getContext('2d'), d = g.createImageData(256, 256);
    for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; }
    g.putImageData(d, 0, 0); return NOISE;
  }
  const BOX = [-50, -124, 112, 134];   // 画一个人要的格子（单位），像素和剪纸先画到这么大的离屏画布上

  function setup(o, h) {
    if (o.who) { const w = WHO[o.who]; o = { ...w, ...o, col: { ...w.col, ...(o.col || {}) } }; }
    O = o; B = BODY[o.age || 'adult']; SK = o.skin || 'line'; LW = 1.3; FW = 1;
    ES = o.eyeStyle === 'anime' ? 1.32 : 1; BD = ES > 1 ? -1.6 : 0;
    const fc = typeof o.face === 'string' ? FACES[o.face] : o.face, fade = o.fade ?? (fc && fc.fade) ?? 0;
    K = {}; Object.entries({ ...COL, ...(o.col || {}) }).forEach(([k, v]) => K[k] = grey(v, fade));
    return o;
  }

  function draw(x, y, h, o = {}) {
    const main = ctx, a = o.a ?? 1; if (a <= 0) return;
    o = setup(o, h); const U = h / 100;
    const flip = o.flip || 1, f = { ...((typeof o.face === 'string' ? FACES[o.face] : o.face) || FACES.calm) };
    const sym = o.sym === undefined ? f.sym : o.sym;
    const view = o.view || 'front';
    const symAt = view === 'back' ? null : [flip * (B.rx + 4), B.top + 4];

    if (SK === 'line') {
      c = main; c.save(); c.globalAlpha *= a; c.translate(x, y); c.scale(U * flip, U);
      const r = body(o); c.restore();
      if (symAt) { c.save(); c.globalAlpha *= a; c.translate(x, y); c.scale(U, U); symbol(sym, symAt[0], symAt[1] + (r.top - B.top)); c.restore(); }
      return;
    }
    // 剪纸、像素：先画到离屏画布
    const px = SK === 'pixel' ? Math.max(2, Math.round(h / 72)) : 1, sc = U / px;
    const W0 = Math.ceil(BOX[2] * sc), H0 = Math.ceil(BOX[3] * sc);
    const off = document.createElement('canvas'); off.width = W0; off.height = H0; c = off.getContext('2d');
    c.save(); c.translate(-BOX[0] * sc, -BOX[1] * sc); c.scale(sc * flip, sc); const r = body(o); c.restore();
    if (symAt) { c.save(); c.translate(-BOX[0] * sc, -BOX[1] * sc); c.scale(sc, sc); symbol(sym, symAt[0], symAt[1] + (r.top - B.top)); c.restore(); }
    if (SK === 'paper') {
      c.save(); c.globalCompositeOperation = 'source-atop'; c.globalAlpha = .07; c.fillStyle = c.createPattern(noise(), 'repeat'); c.fillRect(0, 0, W0, H0); c.restore();
    } else {
      const pal = [...new Set(Object.values(K).concat(['#e8747c', mix(K.top, K.line, .16), mix(K.bottom, K.line, .16), mix(K.shoe, K.line, .16)]))].map(hex);
      const d = c.getImageData(0, 0, W0, H0), p = d.data;
      for (let i = 0; i < p.length; i += 4) {
        if (p[i + 3] < 120) { p[i + 3] = 0; continue; }
        let best = 0, bd = 1e9; for (let j = 0; j < pal.length; j++) { const q = pal[j], dd = (p[i] - q[0]) ** 2 + (p[i + 1] - q[1]) ** 2 + (p[i + 2] - q[2]) ** 2; if (dd < bd) { bd = dd; best = j; } }
        p[i] = pal[best][0]; p[i + 1] = pal[best][1]; p[i + 2] = pal[best][2]; p[i + 3] = 255;
      }
      c.putImageData(d, 0, 0);
    }
    main.save(); main.globalAlpha *= a; main.imageSmoothingEnabled = SK !== 'pixel';
    main.drawImage(off, x + BOX[0] * U, y + BOX[1] * U, W0 * px, H0 * px); main.restore();
    c = main;
  }

  // ---------- 小伙伴「问问」：圆滚滚的软糖身子，头顶一根触角。帽子盖住了主角的呆毛，情绪信号交给它的触角 ----------
  const BUDDY_COL = { body: '#8fd3c1', belly: '#fff3d9', ball: '#f2a63a' };
  const BUDDY_FACES = {
    calm: { eyes: 'dot', mouth: 'w', blush: 1, antenna: 'up' },
    happy: { eyes: 'happy', mouth: 'grin', blush: 1.3, antenna: 'up' },
    puzzled: { eyes: 'dot', mouth: 'o', blush: .8, antenna: 'curl' },
    surprised: { eyes: 'wide', mouth: 'O', blush: .8, antenna: 'up', sym: '!' },
    sad: { eyes: 'dot', mouth: 'frown', blush: .6, antenna: 'droop', tears: 1 },
    spark: { eyes: 'happy', mouth: 'w', blush: 1.3, antenna: 'spark' },
  };
  const BUDDY_B = { eyeR: [5.4, 7.2], rx: 46, eye: [15, -60], brow: -74, mouth: -47, chin: -10, top: -100 };
  function buddy(x, y, h, o = {}) {
    const main = ctx, a = o.a ?? 1; if (a <= 0) return;
    const f = { ...BUDDY_FACES[o.face || 'calm'] }; f.blink = o.blink || 0;
    O = {}; B = BUDDY_B; SK = 'line'; ES = 1; BD = 0; FACE = f;
    K = { ...COL, ...BUDDY_COL, ...(o.col || {}) };
    const u = h / 100, flip = o.flip || 1, lwPx = o.lw ?? h * .043;   // 默认和身高三倍多的主角一样粗
    LW = lwPx / u; FW = LW / 1.3; c = main;
    c.save(); c.globalAlpha *= a; c.translate(x, y); c.scale(u * flip, u);
    const ant = o.antenna || f.antenna;
    // 触角
    const tip = { up: [8, -134], curl: [18, -118], droop: [26, -96], spark: [6, -136] }[ant];
    const stalk = () => {
      c.moveTo(0, -98);
      if (ant === 'curl') { c.bezierCurveTo(-4, -120, 14, -142, 26, -130); c.bezierCurveTo(34, -120, 22, -112, 18, -118); }
      else if (ant === 'droop') c.bezierCurveTo(4, -118, 22, -120, 26, -96);
      else c.bezierCurveTo(-4, -112, 2, -126, tip[0], tip[1]);
    };
    stroke(4 + LW * 2 / FW, K.line, stalk); stroke(4, K.body, stalk);
    if (ant === 'spark') [0, 1, 2, 3, 4, 5].forEach(i => { const an = i / 6 * TAU; stroke(2.4, K.ball, () => { c.moveTo(tip[0] + Math.cos(an) * 10, tip[1] + Math.sin(an) * 10); c.lineTo(tip[0] + Math.cos(an) * 15, tip[1] + Math.sin(an) * 15); }); });
    G(K.ball, () => ell(tip[0], tip[1], 6.5, 6.5));
    // 脚、手、身子、肚皮
    G(K.body, () => { ell(-17, -4, 10, 5.6); ell(17, -4, 10, 5.6); });
    G(K.body, () => { ell(-45, -42, 7, 10.5, .55); ell(45, -42, 7, 10.5, -.55); });
    G(K.body, () => { c.moveTo(-46, -12); c.bezierCurveTo(-48, -72, -34, -100, 0, -100); c.bezierCurveTo(34, -100, 48, -72, 46, -12); c.quadraticCurveTo(0, 2, -46, -12); c.closePath(); });
    fill(K.belly, () => ell(0, -30, 25, 19));
    // 脸
    if (f.blush) [-1, 1].forEach(s => fill(hexA(K.blush, .5 * f.blush), () => ell(s * 28, -50, 7, 4)));
    [-1, 1].forEach(s => eye(s * 15, -60, f.eyes));
    mouth(0, -47, f.mouth, 1);
    if (f.tears) tearDrop(-16, -48, 3);
    c.restore();
    if (f.sym) { c.save(); c.globalAlpha *= a; c.translate(x + flip * h * .5, y - h * 1.1); c.scale(h / 33, h / 33); FW = 1; LW = 1.3; symbol(f.sym, 0, 0); c.restore(); }
  }
  return { draw, buddy, POSES, FACES, COL, BODY, WHO };
})();
function chibi(x, y, h, o = {}) { if (typeof subjectLocal === 'function') subjectLocal('人', x - h * .3, y - h, h * .6, h, (o.a ?? 1) * ctx.globalAlpha); return CHIBI.draw(x, y, h, o); }
function buddy(x, y, h, o = {}) { return CHIBI.buddy(x, y, h, o); }
