// {{系列}}：{{标题}} — 画面。底座是 ../../lib/film.js（时间轴、按词触发、字、人、字幕、renderFrame），它开头写着片子要提供什么、能盖过什么。
// 模板只给流程：调色板、场景、比喻按这篇内容重写（方法/画面规矩.md）。触发挂在词上：w('h1', '具体') 就是这几个字念出来的那一刻。
// 先定样子：字体、小签、字幕、大标题按这篇题材设计，不默认用界面黑体（方法/画面规矩.md质感那几条）。lib 的 pill()、
// drawSubLine()、bigLines() 是默认样子，在这里写同名函数就盖过它；字体可以改 FT.ui（比如 FT.ui = '"Songti SC", serif'）。
// 系列有 样式.js 的，new.sh 已经让 index.html 先载入它。
// 循环写 frac()，列表下标写 mod()：场景淡入时局部时间是负的，% 1 会出负数（./make.sh crash 会查）。

const FADE_IN = 0;    // 推荐流里第一帧就是封面：开场就是完整画面加那句话（规格/平台.md）
const K = {           // 一种颜色一个意思：先写下每种颜色代表什么
  bg0: '#0E1322', ink: '#F2F4F8', dim: '#8A93A8', edge: '#2A3350', panel: 'rgba(16,22,40,.86)', lav: '#B9A7F2',
  accent: '#7FD6C2',  // （例）青绿：这条片子的主干
};

function ground() {
  const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#18213A'); g.addColorStop(1, K.bg0);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
}

// 片尾卡：最后一句说完停一下（script.py 的 END_HOLD），再出片尾卡（END_CARD 秒）
function endCard(lt, sc) {
  if (sc.endHold == null) return;
  const k = fin(lt, sc.endHold - sc.start, .6);
  if (k <= 0) return;
  ctx.save(); ctx.globalAlpha = k; ctx.fillStyle = K.bg0; ctx.fillRect(0, 0, W, H); ctx.restore();
  auditCover(0, 0, W, H, k);
  txt('{{系列}}', CX, CY - 40, { font: `700 96px ${FT.ui}`, color: K.ink, alpha: k, ls: 12 });
}

const SCENE_FN = {
  main: (lt, sc) => {
    const { c, e, w } = Q(sc);
    ground();
    // 开场：HOOK 那句不出字幕，直接是画面上的大字；第一帧画真东西、主体要大（方法/画面规矩.md）。下面的动作只是示范怎么挂在词上
    bigLines([['这一句先写好。', 84, K.ink]], lt, c('h0'), e('h0'), 360, { alpha: fout(lt, e('h0') + .4, .5) });
    // 人一开场就走进来，至少占屏高的四分之一，脚在字幕上方（y 1400 以上）；念到「看完」往前走一步
    const walk = E.out(prog(lt, 0, 1.6)), step = E.inOut(prog(lt, w('h2', '看完') - .1, .8));
    person(lerp(1180, 300, walk) + 90 * step, 1380, 560, { pose: lt < w('h1', '那件事') ? P.stand : P.point });   // 念到「那件事」，他指过去
    // 念到「第二句」一块大板子升上来，念到「具体」上色，念到「拿走」缩到右上角（例：换成这条片子的比喻或证据）
    const up = E.out(prog(lt, w('h1', '第二句') - .2, .7)), fill = fin(lt, w('h1', '具体') - .1, .5);
    const away = E.inOut(prog(lt, w('h2', '拿走') - .1, .8));
    if (up > 0) {
      const x = lerp(470, 840, away), y = lerp(lerp(1500, 620, up), 220, away), sz = lerp(1, .26, away);
      panel(x, y, 520 * sz, 460 * sz, up, { fill: mixHex('#1A2340', K.accent, .55 * fill), edge: K.accent });
    }
    pill('带走', 540, 1180, { alpha: fin(lt, w('h2', '拿走') + .5), color: K.accent });
    // 一直在动的小东西：用 frac()，负的时间也不出错
    circle(160 + 760 * frac(lt * .2), 260, 12, K.accent, .7);
    endCard(lt, sc);
  },
};
