"""The teaser (预告): 30–60 s cut from the finished film, line by line, for the feed and 朋友圈 (大理, 2026-10-17: 47 s from a
19.5-minute film). Nothing new is said or drawn: every picture is a frame of the film, every sound a piece of its mix; the
pieces cross-fade into each other, the last frame holds while the film's own ending music plays out, and one line of text
points to the full film. Picture and sound are cut apart: the picture where the subtitles change, the sound in the pauses
(it may start a little before its picture and end a little after: J- and L-cuts), so no cut lands on a word. Run from a film's folder (make.sh teaser does), after render and mix:
  python3 ../../lib/teaser.py          -> ~/Documents/notes/<time>--<title>-预告__video.mp4, and the checks
  python3 ../../lib/teaser.py check    -> only the plan and the checks, nothing is cut

预告.txt in the film's folder, one piece a line, in order (# starts a comment):
  main.h1            a whole line (scene.line, the ids of script.py / sheet)
  main.d2-d4         a run of lines in one scene
  main.s5#2          one line from its 2nd subtitle line to its end (#2-3: its 2nd and 3rd), counted as on screen
  main.r7  lead=0.6  more of the picture before the voice comes in (seconds; tail= the same after it)
  结尾：完整版 · 在视频号      the line at the end (required: it says where the full film is)
Every cut is checked: it falls in a pause (the dry voice is quiet at the cut and under the fade), and the subtitles on
screen at the first and last frame of a piece are its own.
"""
import glob, json, os, re, subprocess, sys, time
OUT_DIR = __import__("os").environ.get("OUT_DIR") or __import__("os").path.expanduser("~/Documents/notes")   # where finished films go (make.sh mux)
import numpy as np

ROOT = os.getcwd()
LIB = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, 'build')
FPS, SR = 30, 48000
XF = float(os.environ.get('XF', .25))      # the picture's cross-fade between two whole lines (seconds); mid-line cuts are straight
HOLD = float(os.environ.get('HOLD', 2.6))  # how long the last frame holds under the end line, on the film's own last bars
LEAD, TAIL = .25, .45                      # picture before the voice of a piece comes in, and after it ends
QUIET = -45                                # dBFS: the dry voice under this is a pause
TITLE = os.path.basename(ROOT)[8:]

tl = json.load(open(os.path.join(ROOT, 'timeline.json')))
D = tl['duration']
scenes = {s['id']: s for s in tl['scenes']}
order = [(s, c) for s in tl['scenes'] for c in s['cues']]
spans = sorted((s['start'] + c['start'], s['start'] + c['end']) for s, c in order)


def plan():
    p = os.environ.get('PLAN') or os.path.join(ROOT, '预告.txt')
    if not os.path.exists(p):
        sys.exit('没有 预告.txt。在片子文件夹里写一个：一行一段（main.h1、main.d2-d4、main.s5#2），最后一行「结尾：完整版 · 在视频号」。见 lib/teaser.py 开头。')
    pieces, end = [], None
    for raw in open(p, encoding='utf-8'):
        l = re.sub(r'\s+#\s.*$', '', raw.strip())     # a comment: a line starting with #, or « # » after a piece
        if not l or l.startswith('#'):
            continue
        if l.startswith('结尾'):
            end = re.split(r'[：:]', l, 1)[1].strip()
            continue
        ref, *opts = l.split()
        m = re.match(r'^(\w+)\.(\w+)(?:#(\d+)(?:-(\d+))?)?(?:-(\w+))?$', ref)
        if not m or m.group(1) not in scenes:
            sys.exit(f'预告.txt 这一行看不懂：{l}（写成 场.句、场.句-句 或 场.句#块）')
        sc = scenes[m.group(1)]
        ks = [c['k'] for c in sc['cues']]
        k0, k1 = m.group(2), m.group(5) or m.group(2)
        if k0 not in ks or k1 not in ks or ks.index(k1) < ks.index(k0):
            sys.exit(f'预告.txt：{ref} 里的句子不在 {sc["id"]} 场，或者前后颠倒')
        cues = [c for c in sc['cues'] if ks.index(k0) <= ks.index(c['k']) <= ks.index(k1)]
        o = dict(x.split('=', 1) for x in opts if '=' in x)
        pieces.append({'ref': ref, 'sc': sc, 'cues': cues, 'chunks': (int(m.group(3)) if m.group(3) else None, int(m.group(4)) if m.group(4) else None),
                       'lead': float(o.get('lead', LEAD)), 'tail': float(o.get('tail', TAIL))})
    if not pieces:
        sys.exit('预告.txt 里没有一段。')
    if not end:
        sys.exit('预告.txt 缺最后一行「结尾：……」（告诉看的人完整版在哪儿，比如「完整版 · 在视频号」）。')
    return pieces, end


def voice_times(p):
    """when the voice of a piece starts and ends (film seconds), and the subtitle lines it covers"""
    sc, cues = p['sc'], p['cues']
    c0, c1 = cues[0], cues[-1]
    n, m = p['chunks']
    subs0 = c0['subs']
    a, b = sc['start'] + c0['start'], sc['start'] + c1['end']
    own = [x['s'] for c in cues for x in c['subs']]
    p['cut_in'] = p['cut_out'] = False
    if n:                                       # from the n-th subtitle line of the first line on
        if n > len(subs0):
            sys.exit(f"{p['ref']}：{c0['k']} 只有 {len(subs0)} 行字幕")
        if n > 1:
            a, p['cut_in'] = sc['start'] + subs0[n - 1]['t0'], True
        own = [x['s'] for x in subs0[n - 1:]] + [x['s'] for c in cues[1:] for x in c['subs']]
        if m and len(cues) == 1 and m < len(subs0):   # ... up to its m-th
            b, p['cut_out'] = sc['start'] + subs0[m]['t0'] - .06, True
            own = [x['s'] for x in subs0[n - 1:m]]
    return a, b, own


def subs_at(t):
    """the subtitle lines on screen at film time t (the same rule as drawSubs in lib/film.js)"""
    out = []
    for s, c in order:
        lt = t - s['start']
        if lt < c['start'] - .2 or lt > c['end'] + .4:
            continue
        out += [x['s'] for x in c['subs'] if x['t0'] - .03 <= lt <= x['t1'] - .03]
    return out


def dry_voice():
    """the voice alone, from the clips the timeline step saved (quiet where nobody speaks)"""
    v = np.zeros(int((D + 1) * SR), np.float32)
    for s, c in order:
        if os.path.exists(c.get('clip', '')):
            x = np.load(c['clip']).astype(np.float32); i = int((s['start'] + c['start']) * SR)
            v[i:i + len(x)] += x[:max(0, len(v) - i)]
    return v


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12) if len(x) else -120.0


def loud(v, t):
    """the dry voice is speaking at film time t (20 ms around it)"""
    i = int(t * SR)
    return db(v[max(0, i - 480):i + 480]) > QUIET


def voice_on(v, t, lim=1.5):
    """the first moment from t on where the voice speaks (t + lim if none)"""
    k = 0.0
    while k < lim and not loud(v, t + k):
        k += .01
    return t + k


def voice_off(v, t, lim=1.5):
    """the last moment up to t where the voice speaks (t - lim if none)"""
    k = 0.0
    while k < lim and not loud(v, t - k):
        k += .01
    return t - k


def cut_list(pieces):
    """Where every piece starts and ends, picture and sound, and the checks. The picture of a piece runs [a, b] of the film
    and joins the next with a cross-fade (XF) between whole lines, or a straight cut where a line is cut in the middle (its
    subtitle line changes right as the voice starts: no room to fade). The sound runs [sa, sb], cut in the pauses: it may
    lead its picture (sa < a) or stop short of it, and two pieces cross-fade over their overlap, never over a word."""
    v = dry_voice()
    n = len(pieces)
    for p in pieces:
        va, vb, own = voice_times(p)
        p.update(va=va, vb=vb, own=own)
        p['on'], p['off'] = voice_on(v, va - .08), voice_off(v, vb + .08)          # where the voice really starts and ends
        p['prev_off'] = voice_off(v, p['on'] - .03, lim=60) if p['on'] > .1 else 0.0   # the voice before it in the film
        p['next_on'] = voice_on(v, p['off'] + .03, lim=60)                              # and after it
    for p in pieces:
        before = max([e for s, e in spans if e <= p['va'] + .01] or [0.0])
        after = min([s for s, e in spans if s >= p['vb'] - .01] or [D])
        # the picture may not show the line before (its subtitle stays up 0.15 s after it ends) or the one after
        a = max(p['va'] - p['lead'], before + .2 if before > 0 else 0.0, 0.0)
        b = min(p['vb'] + p['tail'], after - .06)
        if p['cut_in']:          # mid-line: the subtitle line before it is up until 0.03 s before the voice
            a = p['va'] - .03 + 1 / FPS
        if p['cut_out']:
            b = p['vb']
        p['a'], p['b'] = round(a * FPS) / FPS, round(b * FPS) / FPS
        p['sa'], p['sb'], p['fin'], p['fout'] = p['a'], p['b'], .01, .01
    xf = max(1, round(XF * FPS)) / FPS                # whole frames: xfade on a 1/30 clock
    d = [0.0] + [1 / FPS if (pieces[i - 1]['cut_out'] or pieces[i]['cut_in']) else xf for i in range(1, n)]
    P = [0.0]                                       # where each picture starts in the teaser
    for i in range(1, n):
        P.append(P[-1] + (pieces[i - 1]['b'] - pieces[i - 1]['a']) - d[i])
    body = P[-1] + pieces[-1]['b'] - pieces[-1]['a']
    for i in range(1, n):
        q, p = pieces[i - 1], pieces[i]
        J = max(0.0, min(.3, p['a'] - (p['prev_off'] + .04)))     # p's sound may lead its picture, in the pause before it
        L = min(0.0, (p['on'] - .02) - p['a'] - d[i])             # q's sound ends before p's voice comes in ...
        L = max(L, -(q['b'] - (q['off'] + .04)))                   # ... but not inside q's own last word
        room = (q['b'] + L) - (q['off'] + .04)                     # the pause after q's voice, inside q's sound
        if L + d[i] + J > room:
            J = max(0.0, room - L - d[i])
        p['sa'], q['sb'] = p['a'] - J, q['b'] + L
        p['fin'] = q['fout'] = max(.01, L + d[i] + J)              # the overlap: one fades out as the other fades in
    # the end: the last frame holds while the film's own last bars play (after its last line)
    last = pieces[-1]
    last['sb'] = max(last['b'], min(last['b'] + .3, last['next_on'] - .04))
    ov = max(.05, min(.3, last['sb'] - (last['off'] + .04)))
    last['fout'] = ov
    t_at = body + (last['sb'] - last['b']) - ov                    # where the last bars come in, on the teaser's clock
    t0 = max(D - (body + HOLD - t_at), max(e for s, e in spans) + .3)
    tail = {'ref': '片尾', 'sa': t0, 'sb': D, 'at': t_at, 'fin': ov, 'fout': .01}
    for i, p in enumerate(pieces):                                 # each piece's sound in step with its own picture
        p['at'] = P[i] + (p['sa'] - p['a'])
    # checks: whose subtitle is on screen at each end of a piece's picture, and whether a fade runs over the voice
    pk = lambda t0_, t1_: max([db(v[k:k + 960]) for k in range(max(0, int(t0_ * SR)), max(int(t0_ * SR) + 1, int(t1_ * SR) - 959), 480)] or [-120])
    rows, bad = [], 0
    for i, p in enumerate(pieces):
        notes = []
        for t in (p['a'], p['b'] - 1 / FPS):
            shown = [s for s in subs_at(t) if s not in p['own']]
            if shown:
                notes.append(f"{t:.2f}s 屏幕上是别段的字幕「{shown[0]}」")
        for t0_, t1_, what in ((p['sa'], p['sa'] + p['fin'], '淡入'), (p['sb'] - p['fout'], p['sb'], '淡出')):
            if t1_ - t0_ > .015 and pk(t0_, t1_) > QUIET:
                notes.append(f"{what}里有人声（{t0_:.2f}–{t1_:.2f}s，{pk(t0_, t1_):.0f} dBFS）：切进了话里")
        if p['b'] - p['a'] < 1.0:
            notes.append('不到 1 秒')
        bad += len(notes)
        rows.append((p, notes, P[i], d[i]))
    return rows, bad, body, tail


def report(rows, bad, end, body, tail):
    print(f'预告：{len(rows)} 段，整句之间画面交叉淡化 {XF} 秒、句中切开的直切，声音在停顿里交叉，片尾停 {HOLD} 秒，最后一行「{end}」')
    for i, (p, notes, at, d) in enumerate(rows):
        how = '' if not i else ('  直切' if d < 2 / FPS else '  淡化')
        lead = f"，声音早 {p['a'] - p['sa']:.2f} 秒进" if p['a'] - p['sa'] > .005 else ''
        print(f"  {at:5.1f}s  {p['ref']:14s} 成片 {p['a']:7.2f}–{p['b']:7.2f}s（{p['b'] - p['a']:4.1f} 秒{lead}）{how}"
              + ('' if not notes else '  !! ' + '；'.join(notes)))
    total = body + HOLD
    print(f"  {body:5.1f}s  片尾：最后一帧停住，配乐是成片最后 {tail['sb'] - tail['sa']:.1f} 秒（{tail['sa']:.1f}–{tail['sb']:.1f}s）")
    print(f'总长 {total:.1f} 秒' + ('' if 30 <= total <= 60 else '：预告 30–60 秒，挑掉几段或补几段'))
    print('检查：' + ('切点都在停顿里，每段首尾的字幕都是自己的' if not bad else f'{bad} 处不对（见上面 !!）：改 预告.txt，或者 lead= / tail= 让一让'))
    return total


def source_video():
    plan_ = os.path.join(BUILD, 'segs.json')
    if os.path.exists(plan_) and json.load(open(plan_))['total'] == int(np.ceil(D * FPS)) and os.path.exists(os.path.join(BUILD, 'segs.txt')):
        return ['-f', 'concat', '-safe', '0'], os.path.join(BUILD, 'segs.txt')
    for f in [os.path.join(BUILD, '成片_高码率.mp4')] + sorted(glob.glob((OUT_DIR + f'/*--{TITLE}__video.mp4')), key=os.path.getmtime, reverse=True):
        if os.path.exists(f):
            return [], f
    sys.exit('找不到成片的画面：先 ./make.sh render（或者成片在 ~/Documents/notes 里）。')


def main():
    pieces, end = plan()
    rows, bad, body, tail = cut_list(pieces)
    total = report(rows, bad, end, body, tail)
    if sys.argv[1:2] == ['check']:
        return
    if bad and os.environ.get('FORCE') != '1':
        sys.exit('有切点不对，先改 预告.txt（确实要这样剪：FORCE=1 ./make.sh teaser）。')
    audio = os.path.join(BUILD, 'audio.wav')
    if not os.path.exists(audio):
        sys.exit('没有 build/audio.wav：先 ./make.sh mix。')
    # the end line, drawn by the film's own page (its font and colours)
    png = os.path.join(BUILD, 'teaser_end.png')
    subprocess.run(['node', os.path.join(LIB, 'capture.mjs'), 'endline', end, png], check=True)
    vin, vsrc = source_video()
    args, g, n = ['ffmpeg', '-y', '-loglevel', 'error'], [], len(rows)
    for i, (p, _, at, d) in enumerate(rows):
        args += ['-ss', f"{p['a']:.4f}", '-t', f"{p['b'] - p['a']:.4f}", *vin, '-i', vsrc]
        # frame-numbered timestamps on a 1/30 clock: with microsecond ones a one-frame xfade is rounded away and the
        # rest of the picture with it (first try: 9.8 s of picture under 33.8 s of sound)
        g.append(f'[{i}:v]fps={FPS},setpts=N/{FPS}/TB,format=yuv420p,settb=1/{FPS}[v{i}]')
    args += ['-loop', '1', '-t', f'{total + 1:.3f}', '-i', png]
    cur = 'v0'
    for i in range(1, n):
        p, _, at, d = rows[i]
        g.append(f'[{cur}][v{i}]xfade=transition=fade:duration={d:.6f}:offset={at:.6f}[x{i}]')
        cur = f'x{i}'
    g.append(f'[{cur}]tpad=stop_mode=clone:stop_duration={HOLD}[vh]')
    g.append(f'[{n}:v]format=rgba,fade=t=in:st={body - .1:.3f}:d=0.5:alpha=1[e]')
    g.append('[vh][e]overlay=0:0:shortest=1,format=yuv420p[vo]')
    raw_v, raw_a = os.path.join(BUILD, 'teaser_video.mp4'), os.path.join(BUILD, 'teaser_audio.wav')
    subprocess.run(args + ['-filter_complex', ';'.join(g), '-map', '[vo]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                           '-r', str(FPS), '-t', f'{total:.3f}', raw_v], check=True)
    # the sound: every piece cut from the mix (sample-exact), faded (equal power), placed on the teaser's clock, summed
    parts, labels = [], []
    for k, s in enumerate([r[0] for r in rows] + [tail]):
        a0, b0 = int(round(s['sa'] * SR)), int(round(s['sb'] * SR)); L = (b0 - a0) / SR
        ch = f"[0:a]atrim=start_sample={a0}:end_sample={b0},asetpts=PTS-STARTPTS,afade=t=in:st=0:d={s['fin']:.4f}:curve=qsin"
        ch += f",afade=t=out:st={max(0.0, L - s['fout']):.4f}:d={s['fout']:.4f}:curve=qsin,adelay=delays={max(0, int(round(s['at'] * SR)))}S:all=1[p{k}]"
        parts.append(ch); labels.append(f'[p{k}]')
    graph = ';'.join(parts) + ';' + ''.join(labels) + f'amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad,atrim=end_sample={int(round(total * SR))}[m]'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', audio, '-filter_complex', graph, '-map', '[m]', '-ar', str(SR), '-c:a', 'pcm_f32le', raw_a], check=True)
    # loudness as the film's: -16 LUFS, true peak -1.5 dBTP (two passes of loudnorm, linear)
    m = subprocess.run(['ffmpeg', '-hide_banner', '-i', raw_a, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    j = json.loads(re.findall(r'\{[^{}]*\}', m)[-1])
    af = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    out = os.environ.get('OUT') or (OUT_DIR + f"/{time.strftime('%Y%m%dT%H%M%S')}--{TITLE}-预告__video.mp4")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw_v, '-i', raw_a, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', af,
                    '-c:a', 'aac', '-b:a', '192k', '-ar', str(SR), '-movflags', '+faststart', out], check=True)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout)
    print(f'{out}\n{dur:.1f} 秒，{os.path.getsize(out) / 1e6:.1f} MB，响度 {j["input_i"]} → -16 LUFS')


if __name__ == '__main__':
    main()
