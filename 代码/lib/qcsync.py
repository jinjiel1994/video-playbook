"""Does the picture land on the sound? For films whose sound is fired by on-screen events (lib/events.js, 方法/声音.md
「声音上的贴」). Reads build/events.json and the cut; every event with vis.probe (a box in 1080×1920 pixels and a colour) is
looked for in the cut: the frame its colour area rises, against floor(t·fps), the frame its sound starts in.
Pass: at least 90% on that same frame and none more than one frame off (a reference film measured 68% same frame, 25% one
early, none late: 案例本/参考/参考片拆解.md「节奏科普爆款」). The audio is reported, not judged: the attack near each event in
build/stem_fx.wav (a sample placed wrong) and in the cut (a mux or AAC offset), each against t.
Run from a film's folder (make.sh qcsync / qc do): python3 ../../lib/qcsync.py [cut.mp4] [--events build/events.json]
[--stem build/stem_fx.wav] [--tol 70]. Needs numpy and ffmpeg."""
import glob, json, os, subprocess, sys
import numpy as np

SAME, MAXOFF, WIN, SCALE = 0.90, 1, 6, 4      # the threshold; frames looked at on each side; decode at 1/SCALE size


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else default


def probe_video(f):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate',
                          '-of', 'json', f], capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]; n, d = s['r_frame_rate'].split('/')
    return s['width'], s['height'], float(n) / float(d)


def frames(f, w, h):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', f, '-vf', f'scale={w}:{h}', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.wait()


def audio(f, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64), sr


def attack(x, sr, t, before=.08, after=.05, frac=.3):
    """The attack start near t: first 1 ms step where a 5 ms RMS envelope rises past frac of the local rise."""
    win, hop = int(.005 * sr), int(.001 * sr)
    a, b = int((t - before - .05) * sr), int((t + after) * sr)
    if a < 0 or b > len(x):
        return None
    env = np.sqrt(np.convolve(x[a:b] ** 2, np.ones(win) / win, 'same')[::hop])
    k0 = int(.05 * sr / hop)                      # the 50 ms before the window: the floor
    base, seg = np.percentile(env[:k0], 20), env[k0:]
    if seg.max() <= base * 1.5 + 1e-6:
        return None
    k = int(np.argmax(seg >= base + frac * (seg.max() - base)))
    return (a + (k0 + k) * hop) / sr


def main():
    pos = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and not sys.argv[i - 1].startswith('--')]
    out_dir = os.environ.get('OUT_DIR') or os.path.expanduser('~/Documents/notes')
    if pos:
        cut = pos[0]
    else:
        c = glob.glob(out_dir + f'/*--{os.path.basename(os.getcwd())[8:]}*__video.mp4')
        if not c:
            sys.exit('没找到成片：python3 qcsync.py <成片.mp4>')
        cut = max(c, key=os.path.getmtime)
    evp = arg('--events', 'build/events.json'); stem = arg('--stem', 'build/stem_fx.wav'); tol = float(arg('--tol', 70))
    ev = json.load(open(evp, encoding='utf-8'))
    meta, events = ev.get('meta', {}), ev['events']
    W0, H0 = meta.get('width', 1080), meta.get('height', 1920)
    vw, vh, fps = probe_video(cut)
    w, h = max(2, vw // SCALE // 2 * 2), max(2, vh // SCALE // 2 * 2)
    sx, sy = w / W0, h / H0
    vis = [e for e in events if (e.get('vis') or {}).get('probe')]
    print(f'成片 {os.path.basename(cut)}：{len(events)} 个事件，{len(vis)} 个带画面探测框（{fps:g} fps）')
    if not vis:
        print('没有带探测框（vis.probe）的事件：不查。事件驱动音效的片子在 EV.build 里给命中的画面写上探测框和颜色')
        sys.exit(0)
    # each event's window: WIN frames each side, cut halfway to the next event in the same box
    for e in vis:
        e['_f0'] = int(np.floor(e['t'] * fps + 1e-6))
        e['_key'] = json.dumps(e['vis']['probe'])
    bykey = {}
    for e in sorted(vis, key=lambda e: e['t']):
        bykey.setdefault(e['_key'], []).append(e)
    need = {}
    for L in bykey.values():
        for i, e in enumerate(L):
            lo, hi = e['_f0'] - WIN, e['_f0'] + WIN
            if i:
                lo = max(lo, (L[i - 1]['_f0'] + e['_f0']) // 2 + 1)
            if i + 1 < len(L):
                hi = min(hi, (e['_f0'] + L[i + 1]['_f0']) // 2)
            e['_lo'], e['_hi'], e['_area'] = lo, hi, {}
            for f in range(max(0, lo - 1), hi + 1):
                need.setdefault(f, []).append(e)
    for i, fr in enumerate(frames(cut, w, h)):
        for e in need.get(i, ()):
            x0, y0, x1, y1 = e['vis']['probe']
            box = fr[int(y0 * sy):max(int(y0 * sy) + 1, int(y1 * sy)), int(x0 * sx):max(int(x0 * sx) + 1, int(x1 * sx))].astype(np.int16)
            c = e['vis'].get('color', '#F14621').lstrip('#'); rgb = np.array([int(c[k:k + 2], 16) for k in (0, 2, 4)])
            e['_area'][i] = int((np.abs(box - rgb).sum(-1) < tol).sum())
            e['_box'] = box.shape[0] * box.shape[1]
    offs, unseen, bad = [], [], []
    for e in vis:
        A = e['_area']; fs = [f for f in range(e['_lo'], e['_hi'] + 1) if f in A]
        if not fs:
            unseen.append(e); continue
        base, peak = min(A.get(f, 0) for f in [e['_lo'] - 1] + fs), max(A[f] for f in fs)
        if peak - base < max(2, .02 * e.get('_box', 1)):
            unseen.append(e); continue
        thr = base + .5 * (peak - base)
        rise = next(f for f in fs if A[f] >= thr and A.get(f - 1, base) < thr) if any(A[f] >= thr and A.get(f - 1, base) < thr for f in fs) else fs[0]
        d = rise - e['_f0']; offs.append(d)
        if abs(d) > MAXOFF:
            bad.append((e, d))
    if offs:
        u, c = np.unique(offs, return_counts=True)
        same = float(np.mean(np.array(offs) == 0))
        print('画面亮起的那一帧 − 声音开始的那一帧：' + '，'.join(f'{int(a):+d} 帧 {b} 个' for a, b in zip(u, c)) + f'（同一帧 {same:.0%}）')
    else:
        same = 0.0
    if unseen:
        print(f'探测框里没看到变化：{len(unseen)} 个（框或颜色不对，或画面没画出来）：' + '，'.join(f"{e.get('id')}@{e['t']:.2f}s" for e in unseen[:12]))
    for e, d in bad[:20]:
        print(f"  差 {d:+d} 帧  {e.get('id')} @ {e['t']:.3f}s  {e.get('src', '')}")
    # the audio: reported, not judged
    snd = [e for e in events if e.get('sfx')]
    for name, f in (('音效轨 stem_fx', stem), ('成片', cut)):
        if not snd or not os.path.exists(f):
            continue
        x, sr = audio(f)
        dt = [(a - e['t']) * 1000 for e in snd for a in [attack(x, sr, e['t'])] if a is not None]
        if dt:
            dt = np.array(dt)
            print(f'{name}：起音 − 事件时间 中位 {np.median(dt):+.1f} ms，四分位 {np.percentile(dt, 25):+.1f}…{np.percentile(dt, 75):+.1f}，'
                  f'差过 5 ms 的 {int((np.abs(dt) > 5).sum())}/{len(dt)}' + ('（音效轨差过 5 ms：样本的起音偏移没扣对）' if name.startswith('音效') and np.median(np.abs(dt)) > 5 else ''))
    ok = bool(offs) and same >= SAME and not bad and not unseen
    print(('通过' if ok else '不通过') + f'：同一帧至少 {SAME:.0%}、没有差过 ±{MAXOFF} 帧的、每个探测框都看到变化')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
