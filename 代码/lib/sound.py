"""The shared sound library: synthesised effects (each returns a stereo or mono array at SR) and add() to place one in a mix.
A film's script.py runs this file after film.py, in its own namespace; its mix() picks what it needs. Add new sounds here."""
import numpy as np
from scipy import signal


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na) ** 2
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return e


def lowpass(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, 'low', fs=SR, output='sos'), x, axis=-1)


def highpass(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, 'high', fs=SR, output='sos'), x, axis=-1)


def bandpass(x, f0, f1, order=2):
    return signal.sosfilt(signal.butter(order, [f0, f1], 'band', fs=SR, output='sos'), x, axis=-1)


def note(name):
    names = {'C': -9, 'D': -7, 'E': -5, 'F': -4, 'G': -2, 'A': 0, 'B': 2}
    k = names[name[0]] + (1 if '#' in name else 0)
    return 440 * 2 ** ((k + 12 * (int(name[-1]) - 4)) / 12)


def reverb_ir(sec, seed, fc=4000):
    n = int(sec * SR); rng = np.random.default_rng(seed)
    ir = np.stack([rng.standard_normal(n), rng.standard_normal(n)]) * np.exp(-np.linspace(0, 7, n))
    ir = lowpass(ir, fc)
    return ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True))


def sweep_noise(dur, seed, f0, f1, shape):
    """Noise through a two-pole low-pass whose cutoff follows f0->f1; shape(p) is the envelope."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR); p = np.linspace(0, 1, n)
    fc = f0 + (f1 - f0) * p
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    out = []
    for ch in range(2):
        x = rng.standard_normal(n); y = np.zeros(n); s1 = s2 = 0.0
        for i in range(n):
            s1 += a[i] * (x[i] - s1); s2 += a[i] * (s1 - s2); y[i] = s2
        out.append(highpass(y, 120) * shape(p))
    o = np.stack(out)
    return o / (np.abs(o).max() + 1e-9)


def whoosh(dur, seed):
    return sweep_noise(dur, seed, 400, 2600, lambda p: np.sin(np.pi * p) ** 2.4)


def riser(dur, seed):
    return sweep_noise(dur, seed, 300, 7000, lambda p: p ** 3)


def thud(depth=1.0):
    n = int(1.0 * SR); t = np.arange(n) / SR
    f = 34 * depth + 30 * np.exp(-t * 10)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    y += lowpass(np.random.default_rng(3).standard_normal(n) * np.exp(-t * 40) * 0.2, 700)
    return np.stack([y, y]) / np.abs(y).max()


def blip(freq, dur=0.09, seed=0):
    """A soft UI 'pop': short sine with a quick pitch drop."""
    n = int(dur * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(freq * (1 + 0.5 * np.exp(-t * 60))) / SR) * np.exp(-t * 38)
    y[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR))
    return np.stack([y, y])


def key_click(seed):
    n = int(0.03 * SR); rng = np.random.default_rng(seed)
    y = bandpass(rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 260), 2000, 7000)
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def shimmer(freqs, dur, seed):
    n = int(dur * SR); t = np.arange(n) / SR; rng = np.random.default_rng(seed)
    L, R = np.zeros(n), np.zeros(n)
    for f in freqs:
        v = np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (1 + .3 * np.sin(2 * np.pi * rng.uniform(3, 6) * t))
        pan = rng.uniform(.2, .8); L += v * (1 - pan); R += v * pan
    return np.stack([L, R]) * env_ar(n, .02, dur * .8) / len(freqs)


def noise_bed(dur, seed, fc, lfo=0.0, depth=0.0):
    n = int(dur * SR); t = np.arange(n) / SR; rng = np.random.default_rng(seed)
    y = lowpass(rng.standard_normal((2, n)), fc, 2)
    if lfo:
        y *= 1 + depth * np.sin(2 * np.pi * lfo * t + rng.uniform(0, 6))
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-9)


def city(dur, seed):
    """Distant traffic: a low bed with cars swelling past now and then."""
    y = noise_bed(dur, seed, 260, 0.05, 0.3) * 0.6
    rng = np.random.default_rng(seed + 1); n = y.shape[1]
    for _ in range(int(dur / 6) + 1):
        c0 = rng.uniform(0, max(0.1, dur - 5)); L = int(rng.uniform(3, 6) * SR); i = int(c0 * SR)
        if i + L >= n:
            continue
        car = lowpass(rng.standard_normal((2, L)), rng.uniform(500, 900)) * (np.sin(np.linspace(0, np.pi, L)) ** 2)
        y[:, i:i + L] += car / (np.abs(car).max() + 1e-9) * rng.uniform(.6, 1.2)
    return y


def glitch(seed):
    n = int(0.35 * SR); rng = np.random.default_rng(seed)
    y = np.repeat(rng.standard_normal(n // 60 + 1), 60)[:n] * (rng.random(n) > .3)
    y = bandpass(y, 800, 6000) * np.exp(-np.linspace(0, 3, n))
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def rustle(dur, seed):
    n = int(dur * SR); rng = np.random.default_rng(seed)
    env = np.abs(lowpass(rng.standard_normal(n), 18)); env /= env.max() + 1e-9
    y = bandpass(rng.standard_normal(n), 1200, 6500) * env * env_ar(n, .05, .2)
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def bell(freq, dur=1.6, vel=1.0):
    """A soft UI bell: a sine with two quiet inharmonic partials."""
    n = int(dur * SR); t = np.arange(n) / SR
    y = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 3.2) + .3 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 9)
         + .12 * np.sin(2 * np.pi * freq * 5.4 * t) * np.exp(-t * 16))
    att = int(.004 * SR); y[:att] *= np.linspace(0, 1, att)
    return np.stack([y, y]) * vel * .5


def pluck(freq, vel=.5, dur=2.6, bright=.55):
    """A plucked string, between a kalimba and a nylon string: the higher harmonics die away first."""
    n = int(dur * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for k in range(1, 8):
        y += (bright ** (k - 1)) / k * np.sin(2 * np.pi * freq * k * t + .4 * k) * np.exp(-t * (1.4 + 1.3 * k))
    att = int(.003 * SR); y[:att] *= np.linspace(0, 1, att)
    return lowpass(y, 5200) * vel


def pad(notes, dur, seed, att=2.2, rel=2.8):
    """A soft held chord: detuned sine pairs with a little octave, slow in and out."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    L, R = np.zeros(n), np.zeros(n)
    for nm in notes:
        f = note(nm)
        for det, pan in ((-.0025, .25), (.0025, .75)):
            v = np.sin(2 * np.pi * f * (1 + det) * t + r.uniform(0, 6)) + .22 * np.sin(2 * np.pi * 2 * f * (1 + det) * t + r.uniform(0, 6))
            v *= 1 + .08 * np.sin(2 * np.pi * r.uniform(.08, .2) * t + r.uniform(0, 6))
            L += v * (1 - pan); R += v * pan
    return lowpass(np.stack([L, R]) * env_ar(n, att, rel) / len(notes), 2200)


def rise_tone(dur, f0, f1):
    """The sound of a loading bar: a soft sine gliding up while it fills."""
    n = int(dur * SR); t = np.arange(n) / SR
    f = np.geomspace(f0, f1, n)
    y = (np.sin(2 * np.pi * np.cumsum(f) / SR) + .3 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)) * env_ar(n, .08, .25) * (.6 + .4 * t / max(dur, 1e-3))
    return np.stack([y, y]) * .5


def thunk():
    """先不加载: a muted low knock that stops the bar."""
    n = int(.5 * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * (95 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 11)
    y += bandpass(np.random.default_rng(4).standard_normal(n), 300, 1600) * np.exp(-t * 60) * .25
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def login_chime():
    out = np.zeros((2, int(2.3 * SR)))
    for i, (nm, v) in enumerate((('A5', .8), ('E6', .9))):
        b = bell(note(nm), 2.0, v); j = int(i * .13 * SR); out[:, j:j + b.shape[1]] += b[:, :out.shape[1] - j]
    return out


def chirp(f0, f1, dur):
    n = int(dur * SR); p = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** p
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * p) ** 1.6


def bird(seed):
    """A small bird outside the window: a few quick whistled notes."""
    r = np.random.default_rng(seed); kind = seed % 3; parts = []
    if kind == 0:
        f = r.uniform(5200, 6800)
        for _ in range(int(r.integers(2, 5))):
            parts += [chirp(f, f * .82, .09), np.zeros(int(.07 * SR))]
    elif kind == 1:
        f = r.uniform(2600, 3400)
        parts += [chirp(f, f * 1.3, .16), np.zeros(int(.05 * SR)), chirp(f * 1.25, f * 1.05, .2)]
    else:
        f = r.uniform(3800, 4800)
        for _ in range(int(r.integers(5, 9))):
            parts += [chirp(f * 1.1, f * .9, .035), np.zeros(int(.018 * SR))]
    y = np.concatenate(parts) * r.uniform(.5, 1); pan = r.uniform(.15, .85)
    return np.stack([y * (1 - pan), y * pan])


def breath(seed=0, t_in=1.5, t_out=2.1):
    e = np.concatenate([np.sin(np.linspace(0, np.pi / 2, int(t_in * SR))) ** 2, np.ones(int(.2 * SR)) * .25, np.cos(np.linspace(0, np.pi / 2, int(t_out * SR))) ** 2 * .9])
    y = bandpass(np.random.default_rng(seed).standard_normal(len(e)), 250, 1700) * e
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def vibrate():
    n = int(.34 * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * 150 * t) * (.6 + .4 * np.sign(np.sin(2 * np.pi * 26 * t))) * env_ar(n, .01, .05)
    return lowpass(np.stack([y, y]), 900)


def shutter():
    out = np.zeros((2, int(.25 * SR)))
    for t0, s, g in ((0, 41, 1.0), (.07, 42, .8)):
        c = key_click(s); i = int(t0 * SR); out[:, i:i + c.shape[1]] += c * g
    n = out.shape[1]
    out += np.stack([bandpass(np.random.default_rng(43).standard_normal(n), 900, 5000)] * 2) * np.exp(-np.arange(n) / SR * 40) * .3
    return out / (np.abs(out).max() + 1e-9)


def lock_click():
    n = int(.4 * SR); t = np.arange(n) / SR
    y = bandpass(np.random.default_rng(8).standard_normal(n), 2500, 8000) * np.exp(-t * 120) * .6
    y += np.sin(2 * np.pi * 2350 * t) * np.exp(-t * 28) * .3 + np.sin(2 * np.pi * 3720 * t) * np.exp(-t * 40) * .2
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def peel(dur=1.2, seed=0):
    """A film coming off a surface: a dry noise sweep with a little crackle."""
    y = sweep_noise(dur, seed, 5000, 1500, lambda p: np.sin(np.pi * p) ** .8)
    r = np.random.default_rng(seed + 1); n = y.shape[1]
    crk = (r.random(n) > .997) * r.standard_normal(n) * 2 * np.linspace(1, .2, n)
    return y + np.stack([crk, crk])


def scribble(dur, seed):
    """The client writing a line by itself: quick dry ticks."""
    n = int(dur * SR); out = np.zeros((2, n)); r = np.random.default_rng(seed); t = 0.0
    while t < dur - .04:
        c = key_click(int(r.integers(0, 999))) * r.uniform(.4, 1); i = int(t * SR); j = min(n, i + c.shape[1])
        out[:, i:j] += c[:, :j - i]; t += r.uniform(.035, .09)
    return out


def add(buf, clip, t0, gain):
    i = int(round(t0 * SR))
    if clip.ndim == 1:
        clip = np.stack([clip, clip])
    if i < 0:
        clip = clip[:, -i:]; i = 0
    j = min(buf.shape[1], i + clip.shape[1])
    if j > i:
        buf[:, i:j] += clip[:, :j - i] * gain


def rumble(dur, seed, speed=1.0):
    """A foam roller on a mat: low filtered noise with the slow wobble of a rolling cylinder."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    y = lowpass(r.standard_normal((2, n)), 260 + 120 * speed, 2) * (1 + .35 * np.sin(2 * np.pi * 3.2 * speed * t))
    y += lowpass(r.standard_normal((2, n)), 1400, 2) * .05 * (r.random((2, n)) > .985)   # the odd creak of foam
    return y / (np.abs(y).max() + 1e-9) * env_ar(n, .25, .35)


def inhale(seed=0, dur=.55):
    """A short sharp in-breath through the teeth: the roller found the spot."""
    n = int(dur * SR); e = np.sin(np.linspace(0, np.pi / 2, n)) ** 2 * np.linspace(1, .3, n) ** .5
    y = bandpass(np.random.default_rng(seed).standard_normal(n), 2200, 7500) * e
    y[-int(.06 * SR):] *= np.linspace(1, 0, int(.06 * SR))
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def exhale(seed=0, dur=2.2):
    """A long out-breath."""
    n = int(dur * SR); e = np.concatenate([np.linspace(0, 1, int(.25 * SR)) ** 2, np.cos(np.linspace(0, np.pi / 2, n - int(.25 * SR))) ** 1.5])
    y = bandpass(np.random.default_rng(seed).standard_normal(n), 300, 1800) * e
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def sea(dur, seed):
    """Waves on a beach at dusk: low noise in slow swells, with a little hiss as each one breaks."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    sw = .55 + .45 * np.sin(2 * np.pi * .11 * t + r.uniform(0, 6)) ** 2
    y = lowpass(r.standard_normal((2, n)), 520, 2) * sw
    y += highpass(lowpass(r.standard_normal((2, n)), 5200, 2), 1800) * .18 * np.maximum(0, np.sin(2 * np.pi * .11 * t + 1.2)) ** 6
    return y / (np.abs(y).max() + 1e-9)


def clink(seed=0):
    """A coin: two bright metal partials, a quick tick on top."""
    n = int(.5 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed); f = r.uniform(2500, 3000)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 22) + .6 * np.sin(2 * np.pi * f * 1.48 * t) * np.exp(-t * 30) + .3 * np.sin(2 * np.pi * f * 2.3 * t) * np.exp(-t * 45)
    y[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR))
    return np.stack([y, y]) * .5


def wood_tap(seed=0, pitch=1.0):
    """A wooden block set down on a wooden table: a short knock with a few hollow modes (等于没说). pitch < 1 for bigger pieces."""
    n = int(.35 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    y = np.zeros(n)
    for f, a, d in ((620, 1.0, 34), (1480, .55, 48), (2350, .3, 70), (3900, .12, 95)):
        y += a * np.sin(2 * np.pi * f * pitch * r.uniform(.97, 1.03) * t) * np.exp(-t * d)
    y += bandpass(r.standard_normal(n), 1200, 6000) * np.exp(-t * 180) * .6
    y += np.sin(2 * np.pi * 140 * pitch * t) * np.exp(-t * 22) * .35        # the table answering underneath
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def airy(dur, seed=0):
    """A ghost appearing: a soft breathy swell with a faint high shimmer, nothing landing."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    y = bandpass(r.standard_normal((2, n)), 1800, 7000) * e * .5
    for f in (1760, 2640, 3520):
        y += .12 * np.sin(2 * np.pi * f * t + r.uniform(0, 6)) * e
    return y / (np.abs(y).max() + 1e-9)


# ---- water (一口气, 2026-10-12): a river you stand in, waves, things dropped into it, a seal on paper ----
def river(dur, seed):
    """A slow river heard from inside it: low flowing noise with a gentle drift, a faint trickle on top."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    y = lowpass(r.standard_normal((2, n)), 380, 2) * (.75 + .25 * np.sin(2 * np.pi * .07 * t + r.uniform(0, 6)))
    trickle = bandpass(r.standard_normal((2, n)), 1800, 5200) * (r.random((2, n)) > .9965) * 1.6
    y += lowpass(trickle, 4800, 2) * .5
    return y / (np.abs(y).max() + 1e-9)


def lap(seed=0):
    """Water lapping against a chin: a soft short slosh."""
    n = int(.5 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    e = np.sin(np.pi * np.clip(t / .5, 0, 1)) ** 2
    y = bandpass(r.standard_normal((2, n)), 300, 1600) * e
    y += bandpass(r.standard_normal((2, n)), 2000, 6000) * e * .25 * (r.random((2, n)) > .7)
    return y / (np.abs(y).max() + 1e-9)


def splash(seed=0, size=1.0):
    """Something dropped into water: a low plop, then a little spray. size > 1 for heavier things."""
    n = int(.9 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    f = 520 / size
    plop = np.sin(2 * np.pi * (f + 900 * np.exp(-t * 40)) * t) * np.exp(-t * 18)
    spray = bandpass(r.standard_normal(n), 1500, 7000) * np.exp(-t * 9) * (t > .02)
    y = plop * .8 + spray * .5 + lowpass(r.standard_normal(n), 250, 2) * np.exp(-t * 6) * .6
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def blubs(dur, seed=0, rate=7.0):
    """Air escaping under water: a run of small rising blubs."""
    n = int(dur * SR); y = np.zeros(n); r = np.random.default_rng(seed); t0 = 0.0
    while t0 < dur - .08:
        m = int(.07 * SR); tt = np.arange(m) / SR; f = r.uniform(300, 700)
        b = np.sin(2 * np.pi * (f + 900 * tt / .07) * tt) * np.sin(np.pi * tt / .07) ** 2
        i = int(t0 * SR); y[i:i + m] += b[:max(0, min(m, n - i))] * r.uniform(.4, 1)
        t0 += r.exponential(1 / rate) + .03
    y = lowpass(y, 2500, 2)
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def swell(dur=1.6, seed=0):
    """A wave rolling in: a rising low surge that breaks into hiss."""
    n = int(dur * SR); p = np.linspace(0, 1, n); r = np.random.default_rng(seed)
    low = lowpass(r.standard_normal((2, n)), 420, 2) * np.sin(np.pi * np.clip(p * 1.1, 0, 1)) ** 1.5
    hiss = highpass(lowpass(r.standard_normal((2, n)), 6000, 2), 1500) * np.clip((p - .45) / .2, 0, 1) * np.exp(-np.clip(p - .65, 0, 1) * 6)
    y = low + hiss * .5
    return y / (np.abs(y).max() + 1e-9)


def stamp(seed=0):
    """A seal pressed onto paper on a wooden desk: a dull knock and a paper thump."""
    n = int(.4 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    y = np.sin(2 * np.pi * 95 * t) * np.exp(-t * 28) + .5 * np.sin(2 * np.pi * 210 * t) * np.exp(-t * 40)
    y += bandpass(r.standard_normal(n), 400, 3000) * np.exp(-t * 60) * .7
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


# ---- a market counter (吃全, 2026-10-14): food into a basket, colour poured into glass bottles, a receipt printer ----
def pour(dur=.7, seed=0, f0=420, f1=1100):
    """Liquid poured into a glass bottle: a bubbly noise through a resonance that rises as the bottle fills, a few glugs."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed); p = t / dur
    src = r.standard_normal(n) * (.6 + .4 * (r.random(n) > .985))
    fc = f0 * (f1 / f0) ** p
    y = np.zeros(n); s1 = s2 = 0.0; q = .06
    for i in range(n):   # a resonant two-pole band-pass that sweeps up
        w = 2 * np.pi * fc[i] / SR; s1 += w * (src[i] - s1 - q * s2 * 8); s2 += w * s1; y[i] = s2
    y = highpass(y, 200)
    for g in np.sort(r.uniform(.05, .85, 4)) * dur:   # glugs
        m = int(.05 * SR); tt = np.arange(m) / SR; i = int(g * SR)
        b = np.sin(2 * np.pi * r.uniform(250, 420) * tt * (1 + 2 * tt)) * np.sin(np.pi * tt / .05) ** 2
        y[i:i + m] += b[:max(0, min(m, n - i))] * .6 * np.abs(y).max()
    y *= np.sin(np.pi * np.clip(p * 1.15, 0, 1)) ** .7
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def tink(seed=0, pitch=1.0):
    """Two glass bottles touching: a short bright ring."""
    n = int(.45 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed); f = r.uniform(2900, 3400) * pitch
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 16) + .5 * np.sin(2 * np.pi * f * 2.71 * t) * np.exp(-t * 26) + .25 * np.sin(2 * np.pi * f * 5.1 * t) * np.exp(-t * 40)
    y[:int(.002 * SR)] *= np.linspace(0, 1, int(.002 * SR))
    return np.stack([y, y]) * .45


def printer(dur, seed=0):
    """A thermal receipt printer: a small motor buzz and the line ticks of the head."""
    n = int(dur * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    motor = np.sign(np.sin(2 * np.pi * 118 * t)) * .5 + np.sin(2 * np.pi * 236 * t) * .3
    motor = bandpass(motor + r.standard_normal(n) * .2, 300, 2400) * env_ar(n, .03, .06)
    ticks = np.zeros(n); k = 0.0
    while k < dur - .01:
        c = key_click(int(r.integers(0, 999))).mean(0) * .5; i = int(k * SR); j = min(n, i + len(c)); ticks[i:j] += c[:j - i]; k += .045
    y = motor * .6 + ticks
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def basket_drop(seed=0, size=1.0):
    """Something from the market set into a woven plastic basket: a soft low thump and the basket's creak."""
    n = int(.45 * SR); t = np.arange(n) / SR; r = np.random.default_rng(seed)
    y = np.sin(2 * np.pi * (90 / size + 70 * np.exp(-t * 30)) * t) * np.exp(-t * 18)
    y += bandpass(r.standard_normal(n), 1500, 6500) * np.exp(-t * 35) * .35
    y += bandpass(r.standard_normal(n), 500, 1400) * np.exp(-t * 14) * .25
    return np.stack([y, y]) / (np.abs(y).max() + 1e-9)


def ding(seed=0):
    """A shop counter's bell: one bright strike."""
    a, b = bell(note('C7'), 1.8, 1.0), bell(note('G7'), 1.8, .35)
    return a + b
