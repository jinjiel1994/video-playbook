// 示例：一帧一帧 — 画面。底座是 ../../lib/film.js。
// 一张暖色的纸，一排胶片格子跟着「每一帧」长出来，念到「算出来」一个圆升起来，念到「哪个词」弹出一个小签，念到「动」圆跳一下。
// 想看的就两件事：触发挂在词上（w('h1', '算出来')），和 renderFrame(t) 只靠 t 就能算出任意一帧。
FT.ui = '"Noto Sans CJK SC", "Source Han Sans CN", "PingFang SC", sans-serif';
const SERIF = '"Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif';
const FADE_IN = 0;   // 第一帧就是完整画面（推荐流里第一帧就是封面）
const K = {
  bg0: '#F3EBDD', ink: '#2B2620', dim: '#9A8F80', edge: '#CDBFA8', panel: 'rgba(255,250,240,.9)', lav: '#6C5B9E',
  accent: '#C0392B',   // 朱红：只给「算出来的那一下」
  pillFill: 'rgba(255,250,240,.95)', subShade: '52,40,28', subInk: '#FFF8EC', subHl: '#FFB59E', vignette: '70,50,30',
};

function paper() {
  ctx.fillStyle = K.bg0; ctx.fillRect(0, 0, W, H);
  const r = rng(5);
  ctx.save(); ctx.globalAlpha = .06; ctx.fillStyle = '#8A6E4B';
  for (let i = 0; i < 900; i++) ctx.fillRect(r() * W, r() * H, 1 + r() * 2, 1 + r() * 2);   // 纸上的纤维点，每帧一样
  ctx.restore();
}

function endCard(lt, sc) {
  if (sc.endHold == null) return;
  const k = fin(lt, sc.endHold - sc.start, .6);
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k; ctx.fillStyle = K.bg0; ctx.fillRect(0, 0, W, H); ctx.restore();
  auditCover(0, 0, W, H, k);
  txt('video-playbook', CX, CY - 60, { font: `700 88px ${SERIF}`, color: K.ink, alpha: k, ls: 4 });
  txt('一帧一帧算出来的片子', CX, CY + 60, { font: `500 48px ${FT.ui}`, color: K.dim, alpha: k, ls: 6 });
}

const SCENE_FN = {
  main: (lt, sc) => {
    const { c, e, w } = Q(sc);
    paper();
    // 开场大字：这句不出字幕，直接是画面上的字；第一帧就整句亮着（t0、t1 给负数），不等它一个个字打出来
    bigLines([['这条片子，', 92, K.ink], ['没有用剪辑软件。', 92, K.ink]], lt, -1, -.5, 330, { alpha: fout(lt, e('h0') + .6, .5) });
    // 胶片格子：念到「每一帧」开始一格格长出来，每格里写着它是第几帧
    const t0 = w('h1', '每一帧');
    for (let i = 0; i < 6; i++) {
      const a = fin(lt, t0 + i * .12, .35); if (a <= 0) continue;
      const x = 120 + i * 145, y = 760;
      panel(x, y, 125, 170, a, { fill: '#FFF8EC', edge: K.edge, r: 10 });
      const n = Math.max(0, Math.floor(lt * 30) - (5 - i));
      txt(String(n), x + 62, y + 85, { font: `600 44px ${FT.ui}`, color: i === 5 ? K.accent : K.dim, alpha: a, deco: true });
    }
    // 念到「算出来」，一个朱红的圆从纸下面升起来
    const up = E.out(prog(lt, w('h1', '算出来') - .1, .9));
    // 念到「动」，圆跳一下
    const hop = pulse(lt, w('h2', '动') - .05, .5);
    if (up > 0) circle(CX, lerp(1700, 1180, up) - 120 * hop, 120, K.accent, up);
    // 念到「哪个词」，小签弹出来
    const pa = pop(lt, w('h2', '哪个词'));
    if (pa > 0) pill('挂在词上', CX, 1000, { color: K.accent, alpha: clamp(pa), size: 46 });
    // 一直在走的帧号：用 frac()/Math.floor，负的时间也不出错
    txt(`第 ${Math.floor(Math.max(0, lt) * 30)} 帧`, CX, 620, { font: `500 48px ${FT.ui}`, color: K.dim, alpha: fin(lt, t0 - .3, .4), deco: true });
    endCard(lt, sc);
  },
};
