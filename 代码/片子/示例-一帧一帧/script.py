#!/usr/bin/env python3
"""示例：一帧一帧 — 竖屏，十几秒，用来验证这套工具在一台新机器上跑得通。
不配音（ENGINE=est 按字数估时间，人声是静音），配乐和音效全用 lib/sound.py 现场合成，所以不需要任何 API key。
流程照旧：python3 script.py sheet → ENGINE=est python3 script.py tts → ./make.sh check → ./make.sh render → python3 script.py mix → ./make.sh mux
一口气跑完：./跑一遍.sh
"""
import os
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lib')
for _f in ('film.py', 'sound.py'):
    exec(compile(open(os.path.join(LIB, _f)).read(), os.path.join(LIB, _f), 'exec'))

HOOK = '这条片子，没有用剪辑软件'
TRANS = {'dissolve': 1.6}
PRE_K = 0.9
END_HOLD, END_CARD = 1.0, 2.0

SCENES = [
    {'id': 'main', 'min': 7, 'lead': 0.15, 'tail': 0, 'trans': None, 'cues': [
        C('h0', '这条片子，没有用剪辑软件。', 0, 'hook', sub=False),
        C('h1', '每一帧，都是网页画布按时间算出来的。', .35, hl=('算出来',)),
        C('h2', '念到哪个词，画面就动哪一下。', .4),
    ]},
]


def mix():
    """没有配音，只有合成的垫底和三个挂在词上的音效：画、声、话挂在同一个词上。"""
    tl = json.load(open(os.path.join(ROOT, 'timeline.json')))
    D = tl['duration'] + 0.3
    N = int(D * SR)
    music, fx = np.zeros((2, N)), np.zeros((2, N))
    add(music, pad(['D3', 'A3', 'F4'], D, 7, att=1.0, rel=2.0), 0, 0.5)
    sc = tl['scenes'][0]
    q = {c['k']: c for c in sc['cues']}
    w = lambda k, s: sc['start'] + q[k]['ct'][q[k]['text'].index(s)]
    add(fx, whoosh(0.8, 1), w('h1', '每一帧') - 0.3, 0.25)
    add(fx, bell(note('A5'), 1.4), w('h1', '算出来'), 0.35)
    add(fx, blip(880), w('h2', '哪个词'), 0.5)
    add(fx, thud(0.8), w('h2', '动'), 0.4)
    total = music + fx
    fade = int(1.2 * SR)
    total[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    write_mix(total, {'music': music, 'fx': fx})
    print(f'audio ok {D:.1f}s')


if __name__ == '__main__':
    main()
