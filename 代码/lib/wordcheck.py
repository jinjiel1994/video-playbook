# Run from a film's folder (make.sh check does): every word trigger in render.js — w('cue', 'words'[, n]) — must still be
# in that cue's text, and every cue named in c('…') / e('…') / sp('…') must exist. A script edited after the picture was
# written breaks these silently until a still throws (掏钱: the ring version's triggers after the switch to flowers).
import json, re
tl = json.load(open('timeline.json'))
text = {c['k']: c['text'] for s in tl['scenes'] for c in s['cues']}
import glob
src = ''.join(open(f).read() for f in sorted(glob.glob('*.js')) if f not in ('timeline.js',))
bad = 0
for k, sub, n in re.findall(r"(?<![A-Za-z0-9_.])w\('([A-Za-z0-9]+)', '([^']+)'(?:, (\d))?\)", src):
    t = text.get(k)
    if t is None or t.count(sub) < int(n or 0) + 1:
        print('MISSING', k, sub, n or '', '|', t); bad += 1
for k in set(re.findall(r"(?<![A-Za-z0-9_.])(?:c|e|sp)\('([A-Za-z0-9]+)'", src)):
    if k not in text: print('NO CUE', k); bad += 1
# the mix's sounds are timed the same way: wt('scene', 'cue', 'words'[, n]) and cs / ce / sp('scene', 'cue') in script.py
import os
if os.path.exists('script.py'):
    mx = open('script.py').read()
    mx = mx[mx.index('def mix'):] if 'def mix' in mx else ''
    # the scene may be passed as a literal ('main') or a variable (吃全: wt(M, 'h1', …) went unchecked)
    for k, sub, n in re.findall(r"wt\((?:'[A-Za-z0-9]+'|[A-Za-z_]\w*), '([A-Za-z0-9]+)', '([^']+)'(?:, (\d))?\)", mx):
        t = text.get(k)
        if t is None or t.count(sub) < int(n or 0) + 1:
            print('MISSING（混音）', k, sub, n or '', '|', t); bad += 1
    # words fed through a loop: for w_ in ('a', 'b'): … wt('scene', 'cue', w_)  (掏钱: three of these went stale unseen)
    # the loop body may sit on the same line or on the next (indented) one (吃全: a stale word in a two-line loop slipped through);
    # the next line counts only when nothing follows the colon (多问一层: the next line was another loop, and its cue was
    # checked against this loop's words)
    for var, words, body in re.findall(r"for (?:\w+, )?(\w+) in (?:enumerate\()?\(([^)]*)\)\)?:(?:[ \t]*\n[ \t]+)?([^\n]*)", mx):
        for k in re.findall(r"wt\((?:'[A-Za-z0-9]+'|[A-Za-z_]\w*), '([A-Za-z0-9]+)', " + var + r"\b", body):
            for sub in re.findall(r"'([^']+)'", words):
                t = text.get(k)
                if t is None or sub not in t:
                    print('MISSING（混音）', k, sub, '|', t); bad += 1
    for k in set(re.findall(r"(?:cs|ce|sp)\((?:'[A-Za-z0-9]+'|[A-Za-z_]\w*), '([A-Za-z0-9]+)'", mx)):
        if k not in text: print('NO CUE（混音）', k); bad += 1
# words kept in tables rather than in w() calls: any 'cue', 'words' pair of string literals whose first is a cue id, in the
# picture and in the mix (吃全: the shopping list's rows and the mix's list of pours went stale unseen)
src_all = src + (open('script.py').read()[open('script.py').read().index('def mix'):] if os.path.exists('script.py') and 'def mix' in open('script.py').read() else '')
seen_pairs = set()
for k, sub in re.findall(r"'([A-Za-z]+[0-9][A-Za-z0-9]*)', '([^']+)'", src_all):
    if k in text and sub not in text and (k, sub) not in seen_pairs:   # (a list of cue ids is not a pair)
        seen_pairs.add((k, sub))
        if sub not in text[k]:
            print('MISSING（表）', k, sub, '|', text[k]); bad += 1
print(f'按词触发：{bad} 处对不上稿子' if bad else '按词触发：都对得上稿子')
# two ways a picture drifts off the words when the voice changes (掏钱, volc → Gemini: d9's big line 3.6 s early because
# 这股劲儿 came twice and the first was taken; d3, b2 hung on «sentence start + seconds»). Hints, they do not stop the check.
warn = []
for k, sub in sorted(set((k, sub) for k, sub, n in re.findall(r"(?<![A-Za-z0-9_.])w\('([A-Za-z0-9]+)', '([^']+)'(?:, (\d))?\)", src) if not n)):
    if text.get(k, '').count(sub) > 1:
        warn.append(f"  {k}「{sub}」在这句里出现 {text[k].count(sub)} 次，按第一次触发；要第几次就写 w('{k}', '{sub}', n)（n 从 0 数）")
for k, v in sorted(set(re.findall(r"(?<![A-Za-z0-9_.])c\('([A-Za-z0-9]+)'\)\s*\+\s*(\d*\.\d+|\d+)", src))):
    if float(v) >= 1.0:
        warn.append(f"  {k} 挂在「句子开头 + {v} 秒」上：换配音、语速一变就错位，能挂在词上就挂在词上")
if warn:
    print(f'提示（不挡）：{len(warn)} 处触发换了配音容易错位'); print('\n'.join(warn))
if bad: raise SystemExit(1)
