// Event-driven sound: one list of events drives both the picture and the mix (方法/声音.md「声音上的贴」).
// index.html loads this after film.js and before the film's render.js. Nothing happens unless a film calls EV.build().
//
//   EV.build(() => [ ...pattern('x..x..x.', 96, 12.0, 2, { lane: 'kick', sfx: 'wood_tap', gain: .5, vis: { probe: [540, 1180, 620, 1260], color: '#F14621' } }),
//                    onWord(S[0], 'h1', '落', 0, { sfx: 'thud', gain: .4 }) ]);
//
// An event: { id, t (film time, seconds), kind, lane, sfx, args, gain, pan, vis: { probe: [x0, y0, x1, y1] in 1080×1920 pixels, color } }.
// sfx names a function in lib/sound.py (or the film's script.py); args are its keyword arguments. vis.probe is the box where
// the hit shows on screen and its colour, so lib/qcsync.py can find it in the cut. `./make.sh events` writes the list to
// build/events.json (with the timeline's hash); script.py mix() places the samples from it (lib/film.py fx_from_events).
//
// The frame rule: a sound that starts at t is drawn on the frame it starts in, floor(t·FPS). film.js's prog()/fin()/pop()
// start at the trigger, so a hit at t first shows on frame ceil(t·FPS): 0–33 ms late, 16.7 ms on average. For anything with a
// sound, start the drawing from snapT(t) (progHit, hitAge). Hold the hit about 5 frames, then let it decay over about 0.1 s
// (hitEnv). Times are film time: inside a scene function use lt + sc.start.
const EV_FPS = 30;   // capture.mjs renders frame f at f / 30
const EV = { list: [], byLane: {} };
const snapT = t => Math.floor(t * EV_FPS + 1e-6) / EV_FPS;
const hitAge = (t, e) => t - snapT(typeof e === 'number' ? e : e.t);
const hitEnv = (age, hold = 5 / EV_FPS, decay = 0.1) => age < 0 ? 0 : age < hold ? 1 : Math.max(0, 1 - (age - hold) / decay);
const progHit = (t, s, d) => prog(t, snapT(s), d);   // prog() with the start on the sound's own frame

// steps: one character per step ('x' hit, 'X' accent, anything else a rest); div steps per beat (2 = eighths, 4 = sixteenths)
function pattern(steps, bpm, t0, bars = 1, o = {}) {
  const div = o.div || 2, beat = 60 / bpm, out = [];
  for (let b = 0; b < bars; b++) [...steps].forEach((c, i) => {
    if (c !== 'x' && c !== 'X') return;
    const { div: _d, ...rest } = o;
    out.push({ kind: 'hit', ...rest, t: t0 + (b * steps.length + i) * beat / div, accent: c === 'X', src: `pattern:${steps}@${bpm}` });
  });
  return out;
}
// an event on a spoken word: the n-th occurrence of s in cue k of scene sc (Q(sc).w is scene time, events are film time)
function onWord(sc, k, s, n = 0, o = {}) {
  return { kind: 'hit', ...o, t: sc.start + Q(sc).w(k, s, n), src: `w('${k}','${s}'${n ? ',' + n : ''})` };
}
EV.build = fn => {
  const list = fn().filter(Boolean);
  for (const e of list) if (typeof e.t !== 'number' || !isFinite(e.t)) throw new Error(`event ${e.id || e.src}: t is not a number`);
  list.sort((a, b) => a.t - b.t);
  list.forEach((e, i) => { e.id = e.id || `e${i}`; if (e.gain == null) e.gain = .5; });
  EV.list = list; EV.byLane = {};
  for (const e of list) (EV.byLane[e.lane || '-'] ||= []).push(e);
  window.EVENTS = list;
  return list;
};
// the latest event in a lane whose frame has come (for drawing a flash): null before the first one
EV.last = (t, lane = '-') => {
  const L = EV.byLane[lane] || []; let lo = 0, hi = L.length - 1, r = null;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (snapT(L[m].t) <= t + 1e-9) { r = L[m]; lo = m + 1; } else hi = m - 1; }
  return r;
};
// the events of a lane between two times (for drawing a scrolling timeline: x = PH_X + (e.t - t) * PX_PER_S)
EV.between = (a, b, lane = '-') => (EV.byLane[lane] || []).filter(e => e.t >= a && e.t <= b);
