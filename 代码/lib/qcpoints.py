"""The frames the checks look at: every line at its middle and near its end, and every transition a quarter, half and
three quarters of the way through (a transition can show the last scene's text through the next one, or cut a person
in half; one frame in its middle does not catch that). With `moves` (make.sh qc), also frames inside the stretches where
the picture moves a lot (build/qc_moves.json from qcmoves.py: camera moves, a scene sliding away), which can fall between
two lines. Run from a film's folder:
  python3 ../../lib/qcpoints.py         -> 12.5,14.1,...   (the times, for capture.mjs audit / stills)
  python3 ../../lib/qcpoints.py json    -> [[12.5, "hook.h1  念到一半  …"], ...]   (with what each frame is, for the index)
  python3 ../../lib/qcpoints.py json moves"""
import json, os, sys

tl = json.load(open('timeline.json'))
pts = []
for s in tl['scenes']:
    for c in s['cues']:
        for f, w in ((.5, '念到一半'), (.92, '快念完')):
            pts.append([round(s['start'] + c['start'] + (c['end'] - c['start']) * f, 2), f"{s['id']}.{c['k']}  {w}  {c['text']}"])
    if s.get('out'):
        d = tl['trans'][s['trans']]
        for f, w in ((.25, '四分之一'), (.5, '一半'), (.75, '四分之三')):
            pts.append([round(s['out'] + d * f, 2), f"{s['id']} 之后的转场，过了{w}"])
mv = 'build/qc_moves.json'
if 'moves' in sys.argv[1:] and os.path.exists(mv) and os.path.getmtime(mv) >= os.path.getmtime('timeline.json'):
    have = [t for t, _ in pts]
    for a, b in json.load(open(mv)):
        for f, w in ((.5, '一半'),) if b - a < .6 else ((.25, '四分之一'), (.5, '一半'), (.75, '四分之三')):
            t = round(a + (b - a) * f, 2)
            if all(abs(t - h) > .12 for h in have):
                pts.append([t, f'画面在大动（{a:.1f}–{b:.1f}s，镜头在移或大块东西进出），过了{w}']); have.append(t)
pts.sort(key=lambda p: p[0])
print(json.dumps(pts, ensure_ascii=False) if 'json' in sys.argv[1:] else ','.join(str(t) for t, _ in pts))
