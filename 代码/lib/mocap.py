#!/usr/bin/env python3
"""CMU 动捕库（mocap.cs.cmu.edu）的 ASF/AMC → 画面上的光点人：逐帧的关节坐标，侧面看，2D。运动片（2026-10-18）写的，挪进 lib。
在片子的文件夹里跑，写进它的 data/动作_<名字>.js（window.MOTION[名字]；index.html 里一个动作载入一行，
画法看运动片 draw.js 的 poseAt、place、figure）：

  python3 ../../lib/mocap.py look <骨架.asf> <动作.amc>
      先看一段动捕里都在干什么，好挑片段：每 0.5 秒一行，骨盆高、往前走的速度、两只脚离地多高、膝盖弯多少。
      蹲下去的地方骨盆一下矮一截、膝盖弯到 90 度上下；跑的地方速度两三米每秒、两只脚轮流离地。
  python3 ../../lib/mocap.py <名字> <骨架.asf> <动作.amc> [--from 秒] [--to 秒] [--anchor ankle|root|ankleL|ankleR]
                             [--flip] [--yaw 度] [--climb]
  --from、--to：只取这一截。一段动作里人常会转身（运动片：69_70 搬完箱子转了身、14_31 走进走出），只取正侧面的那截
  --anchor：ankle（默认）原地的动作，两个脚踝钉在地上不滑步；root 走、跑、推拉这种挪地方的，从骨盆往下接，再把着地的
            那只脚压回地面；ankleL / ankleR 单脚站，只钉站着的那只脚（两只脚的平均一钉，抬起来的那只一动，站着的那只就滑）
  --flip：人朝反了，翻过来
  --yaw：不从正侧面看，绕竖轴转这么多度（扭身从正侧面看不出来，斜四十度看得出肩膀和胯错开）
  --climb：爬楼。找循环时连骨盆的高度一起去掉比，接缝处把升高的那一截接着算（loopRise）

原始文件放片子的 素材/cmu/。CMU 的条款：能放进商业作品；数据不能转卖，转换过的也不行，所以 素材/cmu/ 和转出来的 data/
都只留在本机（片子的 .gitignore 写上）；用了照它请的原话致谢，原话在 README「真人的动作」。

做了什么：
1. 读骨架和每帧的角度，正向运动学算出每根骨头末端在空间里的位置（CMU 的约定：每根骨头先转到自己的 axis，
   再按 AMC 的角度转，R = 父骨头的 R · C · Rz·Ry·Rx · C⁻¹）。
2. 侧面看：水平轴是人朝的方向（跑步取前进方向，原地的动作取两髋连线和竖直方向的叉积），竖轴朝上；正交投影。
3. 一欧元滤波去抖（Casiez 2012；CMU 是光学动捕，本来就干净，滤得很轻）。
4. 全片同一套骨架比例：按每帧的骨头方向，用一套固定的骨长（CHAIN）在 3D 里重新接起来，再侧面投影（在 2D 里接会把
   朝镜头的锁骨、髋拉长）。换了动作，人还是那个人。
5. 存成 120 帧每秒降到 30 帧每秒（和片子一样），单位是身高（头顶到脚底）= 1，原点在两脚之间的地面。
6. 给画面用的几个时刻（秒，从这一截开头算）：flight 两脚离地、骨盆最高的那一刻（跑步的第一帧停在这儿）；bottoms 每回
   蹲到最低，rep0 第一回从哪儿起，repLen 一回多长；loop 首尾最像的两帧（画面过了 loop 的结尾接回开头，无缝循环），
   loopErr 那两帧差多少，loopTravel、loopRise 一圈往前走了多远、升高了多少（画面接着算）。
"""
import json, math, os, sys
import numpy as np


# ---------- ASF / AMC ----------
def parse_asf(path):
    lines = [l.strip() for l in open(path, encoding='latin-1') if l.strip() and not l.startswith('#')]
    bones, hier, i, units = {}, {}, 0, {}
    root = {'axis': [0, 0, 0], 'order': [], 'position': [0, 0, 0], 'orientation': [0, 0, 0]}
    while i < len(lines):
        l = lines[i]
        if l.startswith(':units'):
            i += 1
            while not lines[i].startswith(':'):
                k, v = lines[i].split()[:2]; units[k] = v; i += 1
            continue
        if l.startswith(':root'):
            i += 1
            while not lines[i].startswith(':'):
                p = lines[i].split()
                if p[0] == 'order': root['order'] = [s.lower() for s in p[1:]]
                elif p[0] in ('position', 'orientation'): root[p[0]] = [float(x) for x in p[1:4]]
                elif p[0] == 'axis': root['axisorder'] = p[1]
                i += 1
            continue
        if l.startswith(':bonedata'):
            i += 1
            while not lines[i].startswith(':'):
                if lines[i] == 'begin':
                    b = {'dof': [], 'limits': []}; i += 1
                    while lines[i] != 'end':
                        p = lines[i].split()
                        if p[0] == 'name': b['name'] = p[1]
                        elif p[0] == 'direction': b['direction'] = np.array([float(x) for x in p[1:4]])
                        elif p[0] == 'length': b['length'] = float(p[1])
                        elif p[0] == 'axis': b['axis'] = [float(x) for x in p[1:4]]; b['axisorder'] = p[4]
                        elif p[0] == 'dof': b['dof'] = [s.lower() for s in p[1:]]
                        i += 1
                    bones[b['name']] = b
                i += 1
            continue
        if l.startswith(':hierarchy'):
            i += 1
            while i < len(lines) and not lines[i].startswith(':'):
                p = lines[i].split()
                if p[0] not in ('begin', 'end'): hier[p[0]] = p[1:]
                i += 1
            continue
        i += 1
    return {'bones': bones, 'hier': hier, 'root': root, 'units': units}


def parse_amc(path):
    frames, cur = [], None
    for l in open(path, encoding='latin-1'):
        l = l.strip()
        if not l or l.startswith('#') or l.startswith(':'): continue
        if l.isdigit():
            cur = {}; frames.append(cur); continue
        p = l.split(); cur[p[0]] = [float(x) for x in p[1:]]
    return frames


def rx(a): c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def ry(a): c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
def rz(a): c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def euler_xyz(ax, ay, az): return rz(az) @ ry(ay) @ rx(ax)   # CMU: rotate about x, then y, then z (fixed axes)


def fk(asf, fr):
    """Every bone's end point (and the root) for one AMC frame."""
    bones, hier, root = asf['bones'], asf['hier'], asf['root']
    vals = fr['root']; order = root['order']
    t = np.zeros(3); r = [0.0, 0.0, 0.0]
    for k, v in zip(order, vals):
        if k.startswith('t'): t['xyz'.index(k[1])] = v
        else: r['xyz'.index(k[1])] = math.radians(v)
    Rroot = euler_xyz(*r)
    pos, rot = {'root': t}, {'root': Rroot}
    stack = list(hier.get('root', []))
    parent = {c: 'root' for c in stack}
    for p, cs in hier.items():
        for c in cs: parent[c] = p
    order_bones = []
    def walk(n):
        for c in hier.get(n, []): order_bones.append(c); walk(c)
    walk('root')
    for b in order_bones:
        B = bones[b]
        C = euler_xyz(*[math.radians(a) for a in B['axis']])
        ang = [0.0, 0.0, 0.0]
        for k, v in zip(B['dof'], fr.get(b, [])):
            ang['xyz'.index(k[1])] = math.radians(v)
        M = euler_xyz(*ang)
        R = rot[parent[b]] @ C @ M @ C.T
        rot[b] = R
        pos[b] = pos[parent[b]] + B['length'] * (R @ B['direction'])
    return pos


# ---------- the joints the picture draws ----------
# name: (bone whose END is the joint). 'root' is the middle of the pelvis.
JOINTS = {
    'pelvis': 'root', 'hipL': 'lhipjoint', 'kneeL': 'lfemur', 'ankleL': 'ltibia', 'ballL': 'lfoot', 'toeL': 'ltoes',
    'hipR': 'rhipjoint', 'kneeR': 'rfemur', 'ankleR': 'rtibia', 'ballR': 'rfoot', 'toeR': 'rtoes',
    'waist': 'lowerback', 'chest': 'upperback', 'neck': 'thorax', 'throat': 'lowerneck', 'skull': 'upperneck', 'head': 'head',
    'shoulderL': 'lclavicle', 'elbowL': 'lhumerus', 'wristL': 'lradius', 'handL': 'lhand',
    'shoulderR': 'rclavicle', 'elbowR': 'rhumerus', 'wristR': 'rradius', 'handR': 'rhand',
}
# the chain the canonical skeleton is rebuilt along: (child, parent, canonical length in body heights)
# lengths: a man of average build, measured head-top to sole = 1 (Drillis & Contini's segment ratios, rounded)
CHAIN = [
    ('hipL', 'pelvis', .052), ('kneeL', 'hipL', .245), ('ankleL', 'kneeL', .246), ('ballL', 'ankleL', .085), ('toeL', 'ballL', .03),
    ('hipR', 'pelvis', .052), ('kneeR', 'hipR', .245), ('ankleR', 'kneeR', .246), ('ballR', 'ankleR', .085), ('toeR', 'ballR', .03),
    ('waist', 'pelvis', .07), ('chest', 'waist', .085), ('neck', 'chest', .13), ('throat', 'neck', .035), ('skull', 'throat', .04),
    ('head', 'skull', .09),
    ('shoulderL', 'neck', .1), ('elbowL', 'shoulderL', .186), ('wristL', 'elbowL', .146), ('handL', 'wristL', .06),
    ('shoulderR', 'neck', .1), ('elbowR', 'shoulderR', .186), ('wristR', 'elbowR', .146), ('handR', 'wristR', .06),
]


# ---------- the one-euro filter (Casiez, Roussel & Vogel 2012) ----------
def one_euro(x, fps, mincut=1.6, beta=0.4, dcut=1.0):
    def alpha(cut): te = 1.0 / fps; tau = 1.0 / (2 * math.pi * cut); return 1.0 / (1.0 + tau / te)
    out = np.empty_like(x); out[0] = x[0]; dx_prev = np.zeros_like(x[0])
    for i in range(1, len(x)):
        dx = (x[i] - x[i - 1]) * fps
        ad = alpha(dcut); dx_hat = ad * dx + (1 - ad) * dx_prev
        cut = mincut + beta * np.abs(dx_hat)
        a = alpha(cut)
        out[i] = a * x[i] + (1 - a) * out[i - 1]; dx_prev = dx_hat
    return out


def look(asf_p, amc_p):
    """What happens in a clip, to pick a stretch: one row every 0.5 s (the pelvis height, the speed it travels at, each
    foot's height off the floor, the left knee's bend)."""
    asf = parse_asf(asf_p); amc = parse_amc(amc_p)
    scale = 1 / 0.45 * 2.54 / 100   # CMU length units → metres (units: length 0.45, in inches)
    P = []
    for fr in amc:
        pos = fk(asf, fr)
        P.append([pos[JOINTS[j]] for j in ('pelvis', 'kneeL', 'ankleL', 'hipL', 'toeL', 'toeR', 'head')])
    P = np.array(P) * scale
    floor = np.percentile(np.minimum(P[:, 4, 1], P[:, 5, 1]), 2)
    def knee(i):
        a = P[i, 3] - P[i, 1]; b = P[i, 2] - P[i, 1]
        return 180 - math.degrees(math.acos(np.clip(a @ b / np.linalg.norm(a) / np.linalg.norm(b), -1, 1)))
    print(f'{len(amc)} 帧，{len(amc) / 120:.1f} 秒；身高约 {np.percentile(P[:, 6, 1] - floor, 95) + .1:.2f} 米')
    print('秒    骨盆高  速度m/s  左脚离地 右脚离地  左膝弯')
    for i in range(0, len(amc), 60):
        j = min(len(amc) - 1, i + 60)
        v = np.linalg.norm((P[j, 0, [0, 2]] - P[i, 0, [0, 2]])) / ((j - i) / 120 or 1)
        print(f'{i / 120:5.1f}  {P[i, 0, 1] - floor:5.2f}  {v:6.2f}   {P[i, 4, 1] - floor:6.2f}  {P[i, 5, 1] - floor:6.2f}   {knee(i):5.0f}')


def main():
    a = sys.argv[1:]
    if a[:1] == ['look'] and len(a) >= 3:
        return look(a[1], a[2])
    if len(a) < 3: print(__doc__); sys.exit(1)
    name, asf_p, amc_p = a[:3]
    opt = {a[i]: a[i + 1] for i in range(3, len(a) - 1) if a[i].startswith('--') and not a[i + 1].startswith('--')}
    flip = '--flip' in a
    anchor = opt.get('--anchor', 'ankle')
    climb = '--climb' in a
    yaw = math.radians(float(opt.get('--yaw', 0)))
    asf = parse_asf(asf_p); amc = parse_amc(amc_p)
    fps_in = 120
    f0 = int(float(opt.get('--from', 0)) * fps_in); f1 = int(float(opt.get('--to', len(amc) / fps_in)) * fps_in)
    amc = amc[f0:f1]
    P = []   # frames × joints × 3
    for fr in amc:
        pos = fk(asf, fr)
        P.append([pos[JOINTS[j]] for j in JOINTS])
    P = np.array(P)
    J = list(JOINTS)
    ix = {j: i for i, j in enumerate(J)}
    up = np.array([0, 1, 0.0])
    # facing: travel direction if the root moves far, else from the hips
    travel = P[-1, ix['pelvis']] - P[0, ix['pelvis']]; travel[1] = 0
    lat = (P[:, ix['hipL']] - P[:, ix['hipR']]).mean(0); lat[1] = 0; lat /= np.linalg.norm(lat)
    face = np.cross(lat, up); face /= np.linalg.norm(face)   # left × up points forward
    if np.linalg.norm(travel) > 40:   # moving (ASF units): trust the travel direction
        tr = travel / np.linalg.norm(travel)
        face = tr if np.dot(tr, face) > -0.5 else face
    if flip: face = -face
    if yaw:   # a three-quarter view: turn the line of sight about the vertical
        side = np.cross(up, face); face = math.cos(yaw) * face + math.sin(yaw) * side
    # the canonical skeleton, rebuilt in 3D (bone directions from the capture, lengths from CHAIN), so a bone that points
    # out of the picture plane (collar bones, the hip joints) stays short in the side view, as it should
    src_h = np.percentile(P[:, ix['head'], 1] - np.minimum(P[:, ix['toeL'], 1], P[:, ix['toeR'], 1]), 95)
    k = 1.0 / src_h
    Y3 = np.zeros_like(P)
    Y3[:, ix['pelvis']] = (P[:, ix['pelvis']] - P[0, ix['pelvis']]) * k
    for c, p_, L in CHAIN:
        d = P[:, ix[c]] - P[:, ix[p_]]
        n = np.linalg.norm(d, axis=-1, keepdims=True); n[n < 1e-9] = 1e-9
        Y3[:, ix[c]] = Y3[:, ix[p_]] + d / n * L
    X = np.stack([Y3 @ face, Y3[..., 1]], -1)   # frames × joints × 2: side view, x along the way the body faces
    flat = one_euro(X.reshape(len(X), -1), fps_in, mincut=2.5, beta=0.02)   # a light pass at 120 fps, then 30 fps
    Y = flat.reshape(X.shape)[::4].copy()
    planted = anchor.startswith('ankle')
    if planted:
        # feet planted: pin the mean of the two ankles (or the one standing ankle) to its median spot; then the soles to the ground
        ank = (Y[:, ix['ankleL']] + Y[:, ix['ankleR']]) / 2 if anchor == 'ankle' else Y[:, ix[anchor]]
        Y = Y - (ank - np.median(ank, 0))[:, None, :]
    feet_on = ('ankleL', 'ankleR', 'ballL', 'ballR', 'toeL', 'toeR') if anchor in ('ankle', 'root') else tuple(j + anchor[-1] for j in ('ankle', 'ball', 'toe'))
    low = np.minimum.reduce([Y[:, ix[j], 1] for j in feet_on])
    if planted:
        Y[..., 1] -= np.median(low) - 0.0
    else:
        # running: the foot in contact sits on the ground (the lowest foot point, when it is near its lowest)
        g = np.percentile(low, 5)
        Y[..., 1] -= g
    Y[..., 1] -= -0.012   # the sole is a little below the ankle-ball line
    Y[..., 0] -= np.median((Y[:, ix['ankleL'], 0] + Y[:, ix['ankleR'], 0]) / 2) if planted else Y[0, ix['pelvis'], 0]
    out = {'name': name, 'fps': 30, 'joints': J, 'frames': np.round(Y, 4).tolist(),
           'source': os.path.basename(amc_p), 'from': f0 / fps_in}
    # moments the picture needs (seconds into this clip)
    feet = np.minimum.reduce([Y[:, ix[j], 1] for j in ('ankleL', 'ankleR', 'toeL', 'toeR', 'ballL', 'ballR')])
    pel = Y[:, ix['pelvis'], 1]
    air = np.where(feet > np.percentile(feet, 5) + .02)[0]
    if len(air):   # running: the highest pelvis while both feet are off the ground (the first frame stops here)
        f = air[np.argmax(pel[air])]; out['flight'] = round(f / 30, 3)
    # squats: the bottoms (pelvis lowest) and where each rep starts (pelvis highest before it)
    from scipy.signal import find_peaks
    lows, _ = find_peaks(-pel, prominence=.08, distance=20)
    if len(lows) >= 1:
        out['bottoms'] = [round(f / 30, 3) for f in lows]
        highs, _ = find_peaks(pel, prominence=.08, distance=20)
        starts = [h for h in highs if h < lows[0]]
        out['rep0'] = round((starts[-1] if starts else max(0, lows[0] - 30)) / 30, 3)
        out['repLen'] = round(((lows[1] - lows[0]) if len(lows) > 1 else 60) / 30, 3)

    # a loop the picture can repeat without a jump: two frames (at least a second apart) whose poses match best, the
    # pelvis taken out of the comparison along x (a run travels forward; the picture carries the travel over the seam)
    rel = Y.copy(); rel[..., 0] -= Y[:, ix['pelvis'], 0][:, None]
    if climb: rel[..., 1] -= Y[:, ix['pelvis'], 1][:, None]   # stairs: each round starts one flight higher
    n = len(Y); best = None
    pel_y = Y[:, ix['pelvis'], 1]
    tall = pel_y >= np.percentile(pel_y, 70) if planted else np.ones(n, bool)   # squats: loop standing to standing
    for g0 in range(0, n // 2):
        for g1 in range(g0 + 20, n):   # at least two thirds of a second: one running stride is about 22 frames
            if not (tall[g0] and tall[g1]): continue
            if planted and pel_y[g0:g1].min() > np.percentile(pel_y, 20): continue   # a whole rep, bottom included
            d = np.linalg.norm(rel[g0] - rel[g1], axis=-1).mean()
            if best is None or d < best[0] or (d < best[0] + .002 and g1 - g0 > best[2] - best[1]):
                best = (d, g0, g1)
    if best:
        out['loop'] = [round(best[1] / 30, 3), round(best[2] / 30, 3)]; out['loopErr'] = round(float(best[0]), 4)
        out['loopTravel'] = round(float(Y[best[2], ix['pelvis'], 0] - Y[best[1], ix['pelvis'], 0]), 4)
        if climb: out['loopRise'] = round(float(Y[best[2], ix['pelvis'], 1] - Y[best[1], ix['pelvis'], 1]), 4)
    os.makedirs('data', exist_ok=True)   # the film's folder, where this is run from
    path = os.path.join('data', f'动作_{name}.js')
    open(path, 'w').write(f'window.MOTION = window.MOTION || {{}}; window.MOTION[{json.dumps(name)}] = ' + json.dumps(out) + ';\n')
    print(f'{path}: {len(Y)} 帧（30 fps，{len(Y) / 30:.1f} 秒），来源 {os.path.basename(amc_p)} 从 {f0 / fps_in:.1f} 秒起；'
          + '，'.join(f'{k} {out[k]}' for k in ('flight', 'bottoms', 'rep0', 'repLen', 'loop', 'loopErr', 'loopTravel', 'loopRise') if k in out))


if __name__ == '__main__':
    main()
