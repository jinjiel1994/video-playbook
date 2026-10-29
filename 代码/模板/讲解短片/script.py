#!/usr/bin/env python3
"""{{系列}}：{{标题}} — 竖屏，{{规格}}。{{日期}} 用 ./new.sh 从 模板/讲解短片 起步。
任务书：../../briefs/   口播稿：口播稿.md（先整段写，再切成下面的句子）
片子.json 写着系列、规格、平台、音色、配乐套，lib 拿它当默认值；这里写的同名变量、函数盖过它。
The pipeline is shared: ../../lib/film.py and ../../lib/sound.py run in this file's namespace first.
Commands: python3 script.py export | tts | mix | sheet | hash | gate | listen | qctimes | loudness | mixlu
"""
import os
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lib')
for _f in ('film.py', 'sound.py'):
    exec(compile(open(os.path.join(LIB, _f)).read(), os.path.join(LIB, _f), 'exec'))

# 开头那句：前 5 秒要「奇」或者「有戏」，开口说世界、说别人，不指着观众数落（规格/抖音信息流.md「开头」）。要原样出现在稿子里
HOOK = '这一句先写好'
QUOTE = ''              # 题目来自一本书、一句名言的：那句话大家熟的说法（前 20 秒原样念出来）
TRANS = {'dissolve': 1.6}
PRE_K = 0.9             # 句间停顿整体的倍数（0.85 = 想走得快一点）
END_HOLD, END_CARD = 1.4, 3.0
SUB_WORDS = []          # 这条片子的专名、新词：字幕不会把它们切开
HOLES = ['main.h0']     # 默认混音里配乐让开的句子：开头那句、主干

# 每句一个 C(...)：C('句号', '念的字', 前面停多久, 语速档, sub=False 不出字幕（画面上的大字）, hl=字幕标色的词, py=拼音标注,
# say=送给配音的同音字, emo=情感档)。改一个字都要重审（审稿.md 的哈希）
SCENES = [
    {'id': 'main', 'min': 7, 'lead': 0.15, 'tail': 0, 'trans': None, 'cues': [
        C('h0', '这一句先写好。', 0, 'hook', sub=False),
        C('h1', '接着第二句，把第一句说的那件事说具体。', .35),
        C('h2', '看完这条，你能拿走一样东西。', .4),
    ]},
]

# 配乐按章分段的，不用自己写 mix()：设 MUSIC_SEAMS = 'chapters'，lib 的默认混音把接缝放进每次换章的转场（DUCK、DIPS、CARD_LIFT
# 这几样也能调，说明在 lib/film.py，例子是 videos/2026-10-单片-运动-竖屏/script.py）
# 有了自己的音效、要按句子分段配乐时，在这里写 def mix():（照 videos/2026-10-追本-多问一层-竖屏/script.py 的 mix），lib 的默认混音就让开

if __name__ == '__main__':
    main()
