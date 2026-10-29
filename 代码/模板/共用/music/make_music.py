"""{{标题}} 的配乐：Lyria 3.5 生成，按内容分段，每段一种情绪，全片同一个调、同一个速度，段和段接得上。
两套乐器盲听（带旁白，./make.sh musictry）：A 闷音电吉他（车间的默认，盲听选过三次），B 试一样新的（写进 INST['B']）。
提示词写短，长了容易被拦。生成完 ./make.sh music 会自动查有没有混进人声。默认混音（lib/film.py 的 mix）按 A1、A2… 的顺序接，接缝在全片等分处的停顿里；按章节分段的，
script.py 设 MUSIC_SEAMS = 'chapters'，接缝放进换章的转场。"""
import subprocess, sys, os, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
COMMON = 'Instrumental only, no vocals. Key of D, 76 BPM. Sparse, leave room for a narrator.'
SEC = {   # 段：它垫在哪一段话底下（按话的情绪分，不只按章节）
    '1': 'Quiet and curious, a single question hanging in the air, a soft steady pulse.',
    '2': 'Warm and resolved, bright, ending softly.',
}
SHORT = {}   # 某段的提示词被拦时换一句短的
INST = {'A': 'Muted electric guitar with warm bass and very soft brushed drums, unhurried.',
        'B': ''}   # B 套：这条片子要试的另一种乐器


def one(g, k):
    out = os.path.join(HERE, f'{g}{k}')
    if not INST[g] or any(os.path.exists(out + e) for e in ('.mp3', '.wav')):
        return None
    prompts = [f'{INST[g]} {SEC[k]} {COMMON}']
    if k in SHORT:
        prompts.append(f'{INST[g]} {SHORT[k]} Instrumental, no vocals. Key of D, 76 BPM.')
    prompts.append(f'{INST[g]} {SHORT.get(k, SEC[k])} Instrumental.')
    for attempt, prompt in enumerate(prompts * 2):   # Lyria sometimes blocks a take (content_blocked): a fresh take, then a shorter prompt
        if subprocess.run([sys.executable, f'{ROOT}/engines/gemini.py', 'music', out + '.mp3', prompt]).returncode == 0:
            return f'{g}{k}: ok' + (f' (prompt {attempt % len(prompts) + 1})' if attempt else '')
        print(f'  {g}{k}: blocked, trying again ({attempt + 1})', flush=True)
    return f'{g}{k}: FAILED'


todo = [(g, k) for g in 'AB' for k in SEC]
with cf.ThreadPoolExecutor(4) as ex:
    for res in ex.map(lambda a: one(*a), todo):
        if res: print(res, flush=True)
