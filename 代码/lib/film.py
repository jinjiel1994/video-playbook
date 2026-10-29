"""The shared pipeline of every film: voicing, timings, subtitles, the review gate, the spot-check reel, QC.

A film's script.py runs this file and sound.py inside its own namespace first (see the two lines at its top), then
sets its own voice direction, transitions, SCENES and mix(), and ends with main(). Anything the film defines again
replaces the shared version, the way the film's render.js sits on top of lib/film.js.

  python3 script.py export      -> build/cues.json (the voicing to-do list)
  ENGINE=itts python3 script.py tts   -> timeline.json / timeline.js from the voiced clips + FunASR timings
  ENGINE=est python3 script.py tts    -> the same from estimated timings, before anything is voiced
  python3 script.py mix         -> build/audio.wav (the film's own mix())
  python3 script.py sheet | hash | gate | listen | try ids | qctimes | loudness [file] | mixlu (the stems' loudness again)
  python3 script.py subcheck    -> the subskip keys that leave out no subtitle piece (make.sh check runs it, fails on any)

Each cue is synthesised as a whole sentence so the intonation stays natural; a '|' in the text marks
where an extra dramatic pause is inserted, at the gap between the two words around it.
Word timings drive subtitles (one line at a time) and let the picture react to specific words.
"""
import asyncio, hashlib, json, math, os, subprocess, sys, time, wave
OUT_DIR = __import__("os").environ.get("OUT_DIR") or __import__("os").path.expanduser("~/Documents/notes")   # where finished films go (make.sh mux)
import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, 'build')
os.makedirs(BUILD, exist_ok=True)
SR = 48000
VOICE = 'zh-CN-YunxiNeural'
ENGINE = os.environ.get('ENGINE', 'itts')          # 'itts' (the voiced clips + FunASR timings), 'est' (no recording yet: timings estimated from the text) or 'edge' (old draft voice)
ITTS = os.path.join(BUILD, 'itts')
# whose voice: 'itts' (IndexTTS-2.5 cloning the AISHELL-3 speaker SSB0407), 'gemini:<voice>' (a Gemini TTS preset voice)
# or 'volc:<speaker>' (Doubao Speech: a 2.0 preset voice, or a cloned voice S_xxx / S_xxx:expressive; see engines/volc.py).
# Set VOICE in the environment, or write it in voice.txt next to this script so every step uses the same one.
# 片子.json (written by new.sh): which series and spec the film is, and the defaults that come with them (voice, tone,
# music set, rough length). Each is only a default: voice.txt, the film's own script.py and its own mix() still win.
_fj = os.path.join(ROOT, '片子.json')
FILM = json.load(open(_fj, encoding='utf-8')) if os.path.exists(_fj) else {}
SPEC = FILM.get('规格', '抖音信息流')     # a film from before 片子.json was made to the Douyin feed's rules
# the specs that live in Douyin's feed: the opening gates (HOOK, QUOTE) stop the voicing there and only warn elsewhere
FEED_SPECS = ('抖音信息流', '讲解长片', '切片')
FEED = SPEC in FEED_SPECS
_vf = os.path.join(ROOT, 'voice.txt')
VOICE_SRC = os.environ.get('VOICE') or (open(_vf).read().strip() if os.path.exists(_vf) else '') or FILM.get('音色', '') or 'itts'
GEM_VOICE = VOICE_SRC.split(':', 1)[1] if VOICE_SRC.startswith('gemini:') else None
VOLC_VOICE = VOICE_SRC.split(':', 1)[1] if VOICE_SRC.startswith('volc:') else None
ITTS_DUR = {'normal': 1.04, 'slow': 1.12, 'slower': 1.2, 'hook': 1.08}   # IndexTTS duration_factor per rate
RATES = {'normal': '-3%', 'slow': '-10%', 'slower': '-18%', 'hook': '-6%'}
HOLD = 0.5
SUB_BREAK = '，。：；？！、'
PUNCT = set(SUB_BREAK + '“”…—')

# IndexTTS-2.5 emotion vectors, order [happy, angry, sad, afraid, disgusted, melancholic, surprised, calm].
# Kept small: the rest of the emotion still comes from the reference voice (weight 1 - sum).
EMO_ON = os.environ.get('EMO', '1') == '1'
EMO = {
    'warm':   [0.12, 0, 0, 0, 0, 0.06, 0, 0.08],
    'tense':  [0, 0, 0, 0.12, 0, 0.04, 0.06, 0],
    'wry':    [0.16, 0, 0, 0, 0, 0, 0.08, 0],
    'hurt':   [0, 0.08, 0.16, 0, 0, 0.06, 0, 0],
    'tender': [0.08, 0, 0.04, 0, 0, 0.16, 0, 0.04],
    'eerie':  [0, 0, 0, 0.1, 0, 0.06, 0.08, 0.04],
    'firm':   [0.08, 0.04, 0, 0, 0, 0, 0, 0.16],
    'awe':    [0.04, 0, 0, 0, 0, 0.12, 0.1, 0.06],
    'calm':   [0.04, 0, 0, 0, 0, 0.06, 0, 0.2],
    'sharp':  [0.06, 0.06, 0, 0, 0, 0, 0.04, 0.12],
}
THEY = [('他', 'TA')]      # spoken tā, shown as TA


def C(k, t, pre=0.35, rate='normal', hl=(), sub=True, hold=HOLD, disp=(), py=None, emo=None, subskip=(), say=None, subbreak=()):
    # subskip: subtitle pieces left out because the picture already shows those words big (the voice is unchanged). A key
    # is looked for in each piece as shown, and a piece ends at a punctuation mark or a '|' pause: write a key inside one
    # piece, in the words said (a whole sentence with its commas as one key left every piece up). timeline warns about a
    # key that leaves nothing out and check stops on it (subskip_misses)
    # subbreak: words a subtitle piece must start with, for a phrase too long to fit one line (多问一层 a4: 22 characters with
    # no comma, shrunk to 38 px). Display only: not in the script hash, the voice is unchanged
    # say: what the cloud voices (Gemini, Doubao) are sent instead of a word they keep misreading, since they take no pinyin
    # marks: say={'薄肌': '雹肌'} sends 雹 (only ever báo) so 薄 is not read bó (一口气 r1: four takes of 搏击). Subtitles and
    # the read-back still go by the script's own words; it is part of what gets voiced, so it is in the script hash.
    return {'k': k, 't': t, 'pre': pre, 'rate': rate, 'hl': list(hl), 'sub': sub, 'hold': hold,
            'disp': [list(d) for d in disp], 'py': py or {}, 'emo': emo, 'subskip': list(subskip), 'say': dict(say or {}),
            'subbreak': list(subbreak)}


def said(text, say):
    """The text a cloud voice is sent: the script's words with the line's say={} swaps applied."""
    for a, b in (say or {}).items():
        text = text.replace(a, b)
    return text



# ---- the film's own settings: these are defaults, a film's script.py sets its own after running this file ----
# Gemini takes its delivery from a sentence of direction; the text itself is read verbatim
GEM_BASE = '用自然的普通话讲解：清楚、有节奏。不要播音腔，不要夸张。逗号处自然停一下。'
GEM_STRICT = '严格照着文字一字不差地念：不加「嗯」「啊」「那」之类的语气词，不加儿化音，不重复，不增字也不漏字。语气：自然的普通话讲解，清楚、有节奏，不要播音腔，不要夸张。逗号处自然停一下。'
if FILM.get('语气') == '严格逐字':   # the series' tone (系列/*/系列.json); 掏钱's blind listen picked it. script.py may set its own
    GEM_BASE = GEM_STRICT
GEM_EMO = {'warm': '语气温和。', 'wry': '带一点调侃的笑意。', 'firm': '语气笃定、干脆。', 'tender': '轻一点，放慢。', 'hurt': '声音低一点。',
           'calm': '很安静，放慢。', 'awe': '轻声，像忽然看明白了。', 'eerie': '略带悬念。', 'tense': '略紧张。', 'sharp': '一针见血，停顿干脆。'}
GEM_RATE = {'slow': '语速稍慢。', 'slower': '语速更慢，句尾留一点余味。', 'hook': '像讲一件刚发生的事，有画面感。', 'normal': ''}
# Doubao Speech reads the text as written (no added fillers), so it needs no strict version. Its direction defaults to the
# film's GEM_BASE plus the GEM_EMO of the line; a film that wants another one sets VOLC_BASE. Speed is a number, not words.
VOLC_BASE = ''
VOLC_RATE = {'normal': 0, 'slow': -8, 'slower': -15, 'hook': -4}   # speech_rate, -50..100 (100 = twice as fast)
TRANS = {'dissolve': 1.6}    # a film adds its chapter transition, e.g. {'shutter': 3.2, 'dissolve': 1.6} (seconds)
BEAT = 1.0
PRE_K = 1.0           # every pause before a line is multiplied by this (0.85 = a film meant to move)
END_HOLD, END_CARD = 3.0, 4.6   # after the last line: hold, then the end card
# A rough idea of the length, in seconds, from the spec in the task. Only for reference: sheet prints the estimate against
# it, nothing is held back for running long. Length follows
# the content; cut repetition and what is off the line, never examples, links or evidence to make a time.
TARGET = FILM.get('片长参考')
LONG_OK = ''   # no longer needed (kept so old scripts still run)
# A film made from a book or a famous line: the line as people know it (a common translation or the usual wording, not
# our own paraphrase). `gate` will not voice a script that does not say it word for word within the first 20 seconds
# (等于没说: the line came at 2:12, reworded, and the film was meant to be about that very line). QUOTE_LATE_OK =
# '<reason, agreed by whoever signs off>' lets it come later.
QUOTE = ''
QUOTE_LATE_OK = ''
# The opening line that answers 「我为什么要看」 (奇 or 有戏, see 规格/各规格.md and 案例本/参考/开头钩子笔记.md). In the
# feed's specs (FEED) `gate` will not voice a script without one, or one that is not said word for word, finished within the
# first 5 seconds (掏钱 v2: a couple's story for 40 seconds; the business came in at 15 s, the question at 38 s, what you take
# away at 62 s); other specs only get a warning. The first line is read without pauses, so this uses the speaking rate
# (HOOK_CPS), not the whole-film CPS. HOOK_LATE_OK = '<reason, agreed by whoever signs off>'.
HOOK = ''
HOOK_LATE_OK = ''
HOOK_CPS = 4.2   # characters per second while speaking (火山儒雅逸辰 +8 ≈ 4.3, Algieba ≈ 4.7)
CPS = 3.65   # characters per second of finished film, pauses and end card included (挠痒 3.66, 别分析了 3.79, 接梗 3.62)


# ---------------- speech ----------------
def load_wav(path):
    with wave.open(path) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    return sr, x


async def _synth(text, rate):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate=rate, boundary='WordBoundary')
    audio, words = bytearray(), []
    async for ch in comm.stream():
        if ch['type'] == 'audio':
            audio += ch['data']
        elif ch['type'] == 'WordBoundary':
            words.append([ch['offset'] / 1e7, ch['duration'] / 1e7, ch['text']])
    return bytes(audio), words


def emo_vec(cue):
    return EMO[cue['emo']] if (EMO_ON and cue.get('emo')) else None


def itts_key(text, rate, emo=None, py=None):
    # the pronunciation marks are part of the key: change a mark and the line is voiced again
    tag = f'itts|{rate}|{text}' + (f'|{emo}' if emo else '') + (f'|{sorted(py.items())}' if py else '')
    return hashlib.md5(tag.encode()).hexdigest()[:12]


def gem_style(rate_name, emo_name):
    return GEM_BASE + GEM_RATE.get(rate_name, '') + (GEM_EMO.get(emo_name, '') if (EMO_ON and emo_name) else '')


def volc_style(emo_name, voice=None):
    voice = voice or VOLC_VOICE
    if voice.startswith('S_') and not voice.endswith(':expressive'):   # the standard clone model ignores directions
        return ''
    return (VOLC_BASE or GEM_BASE) + (GEM_EMO.get(emo_name, '') if (EMO_ON and emo_name) else '')


def volc_base(text, rate_name, emo_name, voice=None):
    voice = voice or VOLC_VOICE
    style = volc_style(emo_name, voice)
    key = hashlib.md5(f'volc|{voice}|{style}|{VOLC_RATE[rate_name]}|{text}'.encode()).hexdigest()[:12]
    return os.path.join(BUILD, 'volc', voice.replace(':', '_'), 'volc_' + key), style


def clip_base(text, rate_name, emo_name, py, say=None):
    """Where a line's recording lives, for the voice in use; the second value is the cloud style (None for IndexTTS)."""
    if GEM_VOICE:
        style = gem_style(rate_name, emo_name)
        key = hashlib.md5(f'gemini|{GEM_VOICE}|{style}|{said(text, say)}'.encode()).hexdigest()[:12]
        return os.path.join(BUILD, 'gemini', GEM_VOICE, 'gem_' + key), style
    if VOLC_VOICE:
        return volc_base(said(text, say), rate_name, emo_name)
    ev = EMO[emo_name] if (EMO_ON and emo_name) else None
    return os.path.join(ITTS, 'itts_' + itts_key(text, RATES[rate_name], ev, py)), None


def synth(text, rate, emo=None, py=None, cue=None):
    """Cached synthesis -> (mono float32 @SR, words[[start, dur, text]])."""
    base_now = clip_base(text, cue['rate'], cue.get('emo'), cue['py'], cue.get('say'))[0] if (cue and ENGINE == 'itts') else None
    if ENGINE == 'est' or (base_now and os.environ.get('PREVIEW') == '1' and not os.path.exists(base_now + '.wav')):
        # before voicing (or, in a preview, a line not voiced yet): silence of the estimated length, one character every 0.24 s
        t, words = .05, []
        for ch in text:
            if ch in PUNCT:
                t += .3 if ch in '。？！' else .22
                continue
            words.append([round(t, 3), .22, ch]); t += .24
        return np.zeros(int((t + .1) * SR), np.float32), words
    if ENGINE == 'itts':
        base = clip_base(text, cue['rate'], cue.get('emo'), cue['py'], cue.get('say'))[0] if cue else os.path.join(ITTS, 'itts_' + itts_key(text, rate, emo, py))
        wav48 = base + '_48k.wav'
        if not os.path.exists(wav48) or os.path.getmtime(wav48) < os.path.getmtime(base + '.wav'):   # re-voiced since
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', base + '.wav', '-ac', '1', '-ar', str(SR), wav48], check=True)
        _, x = load_wav(wav48)
        return x, json.load(open(base + '.json'))
    key = hashlib.md5(f'{VOICE}|{rate}|{text}'.encode()).hexdigest()[:12]
    mp3, js, wav = (os.path.join(BUILD, f'tts_{key}.{e}') for e in ('mp3', 'json', 'wav'))
    if not (os.path.exists(mp3) and os.path.exists(js)):
        for attempt in range(5):
            try:
                audio, words = asyncio.run(_synth(text, rate))
                if not audio or not words:
                    raise RuntimeError('empty tts result')
                break
            except Exception as e:
                if attempt == 4:
                    raise
                print('  tts retry', attempt + 1, e); time.sleep(2 + attempt * 2)
        open(mp3, 'wb').write(audio)
        json.dump(words, open(js, 'w'), ensure_ascii=False)
    if not os.path.exists(wav):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp3, '-ac', '1', '-ar', str(SR), wav], check=True)
    _, x = load_wav(wav)
    return x, json.load(open(js))


def char_times(text, words):
    """Start time of every character of `text` (punctuation gets the end of the word before it)."""
    n = len(text); t = [None] * n; i = 0; ends = []
    for off, dur, w in words:
        j = text.find(w, i)
        if j < 0:
            continue
        for q in range(len(w)):
            t[j + q] = off + dur * q / len(w)
        ends.append((j + len(w), off + dur))
        i = j + len(w)
    last = 0.0
    for q in range(n):
        if t[q] is None:
            prev = [e for (ci, e) in ends if ci <= q]
            t[q] = prev[-1] if prev else last
        last = t[q]
    return t, ends


def squeeze_gaps(x, t, ends, cap=0.62):
    """IndexTTS sometimes stalls ~1 s at a comma; shorten any natural pause longer than `cap` from its middle."""
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode='same')
    d = np.diff(np.concatenate([[0], (env < 10 ** (-40 / 20)).astype(np.int8), [0]]))
    runs = [(a, b) for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0])
            if a > int(.1 * SR) and b < len(x) - int(.05 * SR) and (b - a) / SR > cap]
    for a, b in reversed(runs):
        cut = (b - a) - int(cap * SR); m = a + (b - a - cut) // 2
        x = np.concatenate([x[:m], x[m + cut:]])
        tc, dt = m / SR, cut / SR
        t = [v - dt if v > tc else v for v in t]
        ends = [(ci, e - dt if e > tc else e) for ci, e in ends]
    return x, t, ends


def build_cue(cue):
    raw = cue['t']
    parts = raw.split('|')
    text = ''.join(parts)
    x, words = synth(text, RATES[cue['rate']], emo_vec(cue), cue['py'], cue)
    t, ends = char_times(text, words)
    # trim the lead-in so the first word starts ~50 ms in
    first = max(0.0, words[0][0] - 0.05)
    x = x[int(first * SR):]
    t = [v - first for v in t]
    ends = [(ci, e - first) for ci, e in ends]
    x, t, ends = squeeze_gaps(x, t, ends)
    # dramatic pauses at '|': insert silence in the natural gap between the two words
    splits, split_idx = [], []
    idx = 0
    for p in parts[:-1]:
        idx += len(p)
        nxt = t[idx]
        prev_end = max([e for ci, e in ends if ci <= idx] or [nxt])
        ins = min(nxt, prev_end + 0.5 * max(0.0, nxt - prev_end))
        k = int(ins * SR)
        x = np.concatenate([x[:k], np.zeros(int(cue['hold'] * SR), dtype=x.dtype), x[k:]])
        t = [v + cue['hold'] if v >= ins - 1e-6 else v for v in t]
        ends = [(ci, e + cue['hold'] if e > ins else e) for ci, e in ends]
        splits.append(t[idx]); split_idx.append(idx)
    # trim the tail
    env = np.convolve(np.abs(x), np.ones(480) / 480, mode='same')
    loud = np.where(env > 10 ** (-42 / 20))[0]
    if len(loud):
        x = x[:min(len(x), loud[-1] + int(0.08 * SR))]
    return text, x.astype(np.float32), t, splits, split_idx


# ---- subtitle lines: where a line of speech is cut into the lines shown one at a time ----
# A phrase between two commas that is too long for one line used to stay whole and shrink the type (多问一层 a4: 22
# characters, 38 px), unless a hand-written subbreak= cut it. Now it is cut at a word boundary (jieba), and the breaks are
# chosen together (dynamic programming, 大理 2026-10-17): as few lines as possible, never right after a 、 in a list, a
# line never ends on a word that leans on the next one (的/和/在/把/让…) or starts with one that leans on the one before
# (了/着/之间, a measure word), and a number stays with its measure word (738年, 二十万单).
SUB_MAX = 13       # how wide a line may be, in Chinese characters (58 px each; joined phrases never go past this)
SUB_FIT = 15.5     # the widest a single phrase may stay whole (past 860 px the type shrinks; 15 characters is 57 px, unseen)
SUB_WORDS = []     # a film's own words that must never be cut: names, places, coined terms (SUB_WORDS = ['吐蕃', '三月街'])
NO_END = {'的', '地', '得', '和', '与', '跟', '及', '在', '把', '被', '让', '叫', '又', '从', '向', '对', '给', '比', '往', '为',
          '是', '就', '也', '还', '都', '很', '最', '更', '这', '那', '每', '各', '其', '因为', '所以', '但是', '可是', '如果',
          '虽然', '而且', '或者', '还是', '以及', '关于', '通过', '对于', '为了', '一个', '这个', '那个', '一种', '这种',
          '那种', '这些', '那些', '一些', '有些', '这样', '那样', '没', '不', '别', '未', '才', '再', '只', '能', '会', '要',
          '想', '可以', '应该', '已经', '正在', '一直', '不够', '不太', '不再', '不能', '不会', '不要', '没有', '太'}
NO_START = {'的', '地', '得', '了', '着', '过', '吗', '呢', '吧', '啊', '呀', '嘛', '么', '们', '之间', '之中', '之后', '之前',
            '以来', '里', '上', '下', '中', '内', '外', '后', '前', '时', '等', '似的', '一样', '而已', '出来', '起来', '下去',
            '上来', '过来', '回来', '进去', '出去', '下来', '上去', '不到', '得到', '不了', '得了', '不出', '得出', '一点',
            '一些', '一下', '个',
            '年', '次', '岁', '米', '公里', '万', '亿', '元', '块', '倍', '度', '家', '件', '条', '张', '种', '位', '层', '遍', '天'}
SOFT_START = {'和', '与', '跟', '及'}
SUB_WORDS_LIB = ['你自己', '我自己', '他自己', '她自己', '它自己', '自己的']   # words jieba splits that a line should not
_NOUN = {'n', 'nr', 'ns', 'nt', 'nz', 'nrt', 'ng', 'vn', 'an', 'eng'}
CLAUSE_START = {'比', '把', '被', '因为', '所以', '但是', '可是', '如果', '虽然', '而且', '然后', '于是', '比如', '就是'}
_NUM = '0-9０-９零一二两三四五六七八九十百千万亿几半多余'
_MEASURE = '个年月日天号次岁米里万亿元块角分秒倍度家人件条张本只层楼步句遍位名份种类项斤克吨升周回场段首部篇页章节杯瓶碗顿口头匹辆台套双批群届代成折亩'
_jieba = None


def _sub_tokens(text):
    """The words of a line and their parts of speech (jieba, with the film's SUB_WORDS kept whole): [(word, tag)], or
    None when jieba is not installed."""
    global _jieba
    if _jieba is None:
        try:
            import jieba, jieba.posseg, logging
            jieba.setLogLevel(logging.WARNING)
            _jieba = jieba
        except ImportError:
            print('提醒：没装 jieba（python3 -m pip install jieba），字幕只在标点处切，太长的短语会缩小字号。')
            _jieba = False
    if not _jieba:
        return None
    for wd in SUB_WORDS + SUB_WORDS_LIB:
        _jieba.add_word(wd)
    # the words from jieba.cut (posseg cuts differently, e.g. 看|出来), each with its tag from the dictionary
    tags = _jieba.posseg.dt.word_tag_tab
    return [(w, tags.get(w) or (_jieba.posseg.lcut(w)[-1].flag if w.strip() else 'x')) for w in _jieba.cut(text, HMM=True)]


def _sub_width(s):
    """How wide a piece of a line is on screen, in Chinese characters: Latin letters and digits are about half as wide,
    a comma inside the line is drawn as two spaces, the punctuation at its end is not drawn."""
    import unicodedata
    s = s.rstrip(SUB_BREAK + ' ')
    w = 0.0
    for c in s:
        w += .6 if c in SUB_BREAK else .3 if c.isspace() else 1.0 if unicodedata.east_asian_width(c) in 'WF' else .55
    return w


def _sub_word_breaks(text, keep=()):
    """Where a phrase too long for one line may be cut, and how bad each place is: {position: cost}. A position p cuts
    text[:p] | text[p:]. keep: words never cut (the highlighted ones; SUB_WORDS too)."""
    import re, unicodedata
    n, glue = len(text), set()
    def hold(a, b):
        glue.update(range(a + 1, b))
    for wd in list(keep) + list(SUB_WORDS):
        for m in re.finditer(re.escape(wd), text):
            hold(m.start(), m.end())
    for m in re.finditer(f'第?[{_NUM}][{_NUM}.,]* ?[{_MEASURE}]', text):   # 738年, 二十万单, 3 个, 第五层
        hold(m.start(), m.end())
    for m in re.finditer(r'[A-Za-z0-9][A-Za-z0-9.\-+#&_%]*', text):         # a Latin word or a number
        hold(m.start(), m.end())
    narrow = lambda c: c.isalnum() and unicodedata.east_asian_width(c) not in 'WF'
    for p in range(1, n):                       # a letter written onto a Chinese word: 维生素A, β胡萝卜素
        if (narrow(text[p - 1]) or narrow(text[p])) and not (text[p - 1].isspace() or text[p].isspace()):
            glue.add(p)
    quoted = set()                      # inside a quote: cut there only if nothing else works
    for m in re.finditer(r'“[^”]*”|「[^」]*」|『[^』]*』|《[^》]*》', text):
        quoted.update(range(m.start() + 1, m.end()))
    tok, cost = _sub_tokens(text), {}
    if not tok:
        return cost
    bounds, k = [], 0
    for w, _ in tok:
        k += len(w); bounds.append(k)
    for i, p in enumerate(bounds[:-1]):
        (prev, pt), (nxt, nt) = tok[i], tok[i + 1]
        if p in glue or (text[p] in PUNCT and text[p] not in '“「『《') or text[p - 1] in '“「『《':
            continue      # a line never starts on punctuation (an opening quote is fine) or ends on an opening quote
        lean = (10 if prev in NO_END else 0) + (10 if nxt in NO_START else 0)
        if text[p] in '“「『《' or text[p - 1] in '”」』》':   # just outside a quote: as good as a pause
            cost[p] = 2.0 + lean
            continue
        if nxt.isspace() or prev.isspace():   # the space between Chinese and a Latin word: a fair place to cut
            cost[p] = 3.0 + (6 if p in quoted else 0)
            continue
        c = 6.0
        c += 10 if prev in NO_END else 0
        c += 10 if nxt in NO_START else 0
        c += 3 if nxt in SOFT_START else 0
        c += 3 if len(nxt) == 1 and not nxt.isascii() else 0      # a one-character word usually leans on the one before
        c += 2 if len(prev) == 1 and not prev.isascii() else 0
        c += 8 if (pt in _NOUN and nt in _NOUN) or (pt == 'r' and nt == 'r') else 0   # 季度|汇报, 你|自己
        c += 6 if pt in ('a', 'm') and nt in _NOUN else 0                            # 好|办法, 几个|星期
        c -= 2 if (nxt in CLAUSE_START or nt in ('p', 'c')) and nxt not in SOFT_START else 0   # a line may start on 对/把/因为…
        c += 6 if p in quoted else 0
        cost[p] = max(c, 1.0)
    return cost


def _sub_split(text, a, b, cost):
    """A phrase too long for one line, cut at its words into pieces of at most SUB_MAX: the fewest pieces, at the least
    bad places, about the same length."""
    pos = [a] + sorted(p for p in cost if a < p < b) + [b]
    best, back = [0.0] + [math.inf] * (len(pos) - 1), [0] * len(pos)
    for j in range(1, len(pos)):
        for i in range(j - 1, -1, -1):
            w = _sub_width(text[pos[i]:pos[j]])
            if w > SUB_MAX and i < j - 1:
                break
            c = 10 + .05 * (SUB_MAX - w) ** 2 if w <= SUB_MAX else 10 + 1e4 * (w - SUB_MAX)   # a single word too long: keep it
            c += cost[pos[j]] if pos[j] < b else 0.0
            if best[i] + c < best[j]:
                best[j], back[j] = best[i] + c, i
    out, j = [], len(pos) - 1
    while j > 0:
        out.append((pos[back[j]], pos[j])); j = back[j]
    return out[::-1]


def sub_lines(text, breaks=(), skip=(), keep=()):
    """How a line of speech is cut into subtitle lines: [(a, b), ...]. Phrases are cut at the punctuation (the pauses of
    speech) and at the forced breaks (a '|' pause, subbreak=); a phrase too wide to show whole is cut at its words
    (_sub_split); then phrases are joined up to SUB_MAX characters a line, as few lines as possible, filling each line
    before the next, except that a line does not end right after a 、 when another way takes no more lines."""
    n = len(text)
    cuts = {i for i in breaks if 0 < i < n}
    phrases, s = [], 0
    for i, ch in enumerate(text):
        if i in cuts and i > s:
            phrases.append((s, i)); s = i
        if ch in SUB_BREAK:
            phrases.append((s, i + 1)); s = i + 1
    if s < n:
        phrases.append((s, n))
    sk = lambda a, b: any(w in text[a:b] for w in skip)
    atoms, cost = [], None                       # (a, b, alone): a piece of a cut phrase stands alone on its line
    for a, b in phrases:
        if _sub_width(text[a:b]) > SUB_FIT and not sk(a, b):
            cost = _sub_word_breaks(text, keep) if cost is None else cost
            pieces = _sub_split(text, a, b, cost)
            atoms += [(p, q, len(pieces) > 1) for p, q in pieces]
        else:
            atoms.append((a, b, False))
    vis = lambda a, b: sum(1 for c in text[a:b] if c not in PUNCT)
    m = len(atoms)
    # from the end: best[i] = (lines, lines ending right after a 、) for atoms[i:]; ties go to the longer first line
    best, nxt = [None] * m + [(0, 0)], [m] * (m + 1)
    for i in range(m - 1, -1, -1):
        for j in range(i + 1, m + 1):
            a, b = atoms[i][0], atoms[j - 1][1]
            if j > i + 1:
                if any(atoms[q][2] for q in range(i, j)) or vis(a, b) > SUB_MAX or atoms[j - 1][0] in cuts \
                        or sk(*atoms[j - 1][:2]) != sk(*atoms[i][:2]):
                    break
            r = (1 + best[j][0], best[j][1] + (j < m and text[b - 1] == '、'))
            if best[i] is None or r <= best[i]:
                best[i], nxt[i] = r, j
    out, i = [], 0
    while i < m:
        out.append((atoms[i][0], atoms[nxt[i] - 1][1])); i = nxt[i]
    return out


def sub_chunks(text, times, end, hl, disp, breaks=(), skip=()):
    # skip: words shown big on screen. A phrase holding one is never merged with its neighbours, so dropping it later
    # (tts) does not take the rest of the line with it (等于没说: 「他的办法：说不了的，就沉默」 lost 「他的办法」)
    chunks = sub_lines(text, breaks, skip, keep=hl)
    shown = lambda c: c not in PUNCT and not c.isspace()
    out = []
    for n, (a, b) in enumerate(chunks):
        a2 = next((i for i in range(a, b) if shown(text[i])), a)
        t0 = times[a2]
        t1 = times[next((i for i in range(chunks[n + 1][0], chunks[n + 1][1]) if shown(text[i])), chunks[n + 1][0])] if n + 1 < len(chunks) else end
        s = text[a:b].rstrip('，。：；、')
        for c in '，：；、。':
            s = s.replace(c, '  ')
        s = s.replace('？', '？ ').strip()
        s = s[1:].lstrip() if s.startswith('”') else s   # a quote mark cut off from its pair at a phrase break
        s = s[:-1].rstrip() if s.endswith('“') else s
        for src, dst in disp:
            s = s.replace(src, dst)
        ranges = []
        for kw in hl:
            p = s.find(kw)
            while p >= 0:
                ranges.append([p, p + len(kw)]); p = s.find(kw, p + 1)
        out.append({'s': s, 't0': round(t0, 3), 't1': round(t1, 3), 'hl': ranges})
    return out


def _sub_pieces(text, a, b, cuts):
    """text[a:b] cut where a subtitle line is cut (its punctuation, a '|' pause, a subbreak=), each piece without the
    punctuation at its ends: what a subskip key has to stay inside."""
    out, s = [], a
    for q in range(a, b + 1):
        if q == b or text[q] in SUB_BREAK or q in cuts:
            out.append(text[s:q])
            s = q + 1 if q < b and text[q] in SUB_BREAK else q
    edge = ''.join(PUNCT) + ' '
    return [p.strip(edge) for p in out if p.strip(edge)]


def subskip_misses():
    """The subskip keys that leave out no subtitle piece, a line each: which line, which key, why, how to write it. A
    piece is left out when a key is in it as shown (sub_chunks: a comma inside it is drawn as two spaces), and the pieces
    end at the punctuation and at the pauses, so a whole sentence with its commas as one key, or words the line does not
    say, match nothing: the subtitle stays up under the same words drawn big, and nothing said so (the film review once found them two rounds running). tts prints these; subcheck stops on them."""
    marks = SUB_BREAK + ',;:?!'
    word = lambda c: c not in PUNCT and c not in marks and not c.isspace()
    out = []
    for sc in SCENES:
        for cue in sc['cues']:
            keys = cue.get('subskip') or []
            if not keys or not cue.get('sub', True):
                continue
            parts = cue['t'].split('|')          # cut the way tts cuts it: at the '|' pauses and the subbreak= words
            text, cuts, n = ''.join(parts), set(), 0
            for p in parts[:-1]:
                n += len(p); cuts.add(n)
            cuts |= {text.index(wd) for wd in cue.get('subbreak', []) if wd in text}
            shown = [ch['s'] for ch in sub_chunks(text, [0.0] * len(text), 0.0, cue.get('hl', []), cue.get('disp', []), cuts, keys)]
            pos = [q for q, c in enumerate(text) if word(c)]
            bare = ''.join(text[q] for q in pos)
            for w in keys:
                if any(w in s for s in shown):
                    continue
                head = f"{sc['id']}.{cue['k']} 的键「{w}」一段字幕都没让掉："
                bw = ''.join(c for c in w if word(c))
                j = bare.find(bw) if bw else -1
                if j < 0:
                    out.append(head + f"这句稿子里没有这几个字（画面上的字和念的不一样，键照念的写）。这句的字幕段是「{'」「'.join(_sub_pieces(text, 0, len(text), cuts))}」，照其中一段写")
                    continue
                a, b = pos[j], pos[j + len(bw) - 1] + 1
                got = _sub_pieces(text, a, b, cuts)
                inkey = ''.join(dict.fromkeys(c for c in w if c in marks))
                intext = ''.join(dict.fromkeys(c for c in text[a:b] if c in SUB_BREAK))
                pause = any(a < q < b and text[q - 1] not in SUB_BREAK for q in cuts)   # a pause right after a comma adds no cut
                if inkey:
                    why = f"键里带了「{inkey}」，字幕在标点处分段，段里的标点显示成空格，带标点的键哪一段都对不上"
                elif intext or pause:
                    why = '稿子在这几个字中间有' + '和'.join(([f'「{intext}」'] if intext else []) + (['停顿（| 或 subbreak）'] if pause else [])) \
                          + f'，字幕在那儿分段，键跨了 {len(got)} 段'
                else:
                    out.append(head + f"字幕显示成「{'」「'.join(shown)}」，里面没有这几个字（disp 换过字？），照显示的一段写")
                    continue
                out.append(head + why + '。按字幕的一段写，不跨标点：' + (f"拆成「{'」「'.join(got)}」" if len(got) > 1 else f'写成「{got[0]}」'))
    return out


def subskip_check():
    """python3 script.py subcheck (make.sh check runs it): the subskip keys that leave out no subtitle; fails on any."""
    n = sum(len(c.get('subskip') or []) for sc in SCENES for c in sc['cues'] if c.get('sub', True))
    miss = subskip_misses()
    if miss:
        print('\n'.join('  ' + m for m in miss))
        print(f'字幕让开（subskip）：{len(miss)} 个键对不上字幕，大字底下照样出字幕。改好键，重跑 ./make.sh timeline 再 check')
        sys.exit(1)
    print(f'字幕让开（subskip）：{n} 个键都对得上字幕' if n else '字幕让开（subskip）：这条片子没写')


def tts():
    t = 0.0
    out = {'trans': TRANS, 'beat': BEAT, 'scenes': []}
    total_chars = speech = 0.0
    for si, sc in enumerate(SCENES):
        start = t
        ct = start + sc['lead']
        cues = []
        for ci, cue in enumerate(sc['cues']):
            ct += cue['pre'] * PRE_K if ci else 0
            text, x, times, splits, split_idx = build_cue(cue)
            dur = len(x) / SR
            clip = os.path.join(BUILD, f"clip_{sc['id']}_{cue['k']}.npy")
            np.save(clip, x)
            loc = ct - start
            entry = {'k': cue['k'], 'text': text, 'start': round(loc, 3), 'end': round(loc + dur, 3),
                     'ct': [round(loc + v, 3) for v in times], 'splits': [round(loc + v, 3) for v in splits],
                     'abs': round(ct, 3), 'clip': clip}
            brk = set(split_idx) | {text.index(wd) for wd in cue.get('subbreak', []) if wd in text}
            entry['subs'] = [ch for ch in sub_chunks(text, [loc + v for v in times], loc + dur + 0.15, cue['hl'], cue['disp'], brk, cue.get('subskip', []))
                             if not any(w in ch['s'] for w in cue.get('subskip', []))] if cue['sub'] else []
            cues.append(entry)
            total_chars += sum(1 for c in text if c not in PUNCT); speech += dur
            ct += dur
        e = {'id': sc['id'], 'name': sc.get('name', ''), 'min': sc.get('min', 7), 'start': round(start, 3), 'cues': cues}
        if sc['trans']:
            e['out'] = round(ct + sc['tail'], 3)
            e['trans'] = sc['trans']
            t = ct + sc['tail'] + TRANS[sc['trans']]
        else:
            e['endHold'] = round(ct + END_HOLD, 3)
            e['end'] = round(ct + END_HOLD + END_CARD, 3)
            t = e['end']
        out['scenes'].append(e)
    out['duration'] = round(t, 3)
    json.dump(out, open(os.path.join(ROOT, 'timeline.json'), 'w'), ensure_ascii=False)
    with open(os.path.join(ROOT, 'timeline.js'), 'w') as f:
        f.write('window.TIMELINE=' + json.dumps(out, ensure_ascii=False) + ';')
    print(f"duration {out['duration']:.1f}s ({out['duration'] / 60:.1f} min)  speech {speech:.1f}s  chars {int(total_chars)}")
    if TARGET:
        print(f"实际 {mmss(out['duration'])}（任务书估的是 {mmss(TARGET)} 左右，只做参考）")
    for s in out['scenes']:
        ln = (s.get('out') or s.get('end')) - s['start']
        print(f"  {s['id']:8s} start {s['start']:6.1f}  len {ln:5.1f}")
    miss = subskip_misses()
    if miss:
        print(f'提醒：字幕让开（subskip）有 {len(miss)} 个键一段字幕都没让掉，大字底下照样出字幕（make.sh check 会拦）：')
        print('\n'.join('  ' + m for m in miss))


def export():
    os.makedirs(ITTS, exist_ok=True)
    cues = []
    for sc in SCENES:
        for c in sc['cues']:
            text = c['t'].replace('|', '')
            tts_text = text.replace('“', '').replace('”', '')
            for ch, py in c['py'].items():
                tts_text = tts_text.replace(ch, f'<{ch}|{py}>')
            ev = emo_vec(c)
            base, style = clip_base(text, c['rate'], c.get('emo'), c['py'], c.get('say'))
            plain = said(text, c.get('say')).replace('“', '').replace('”', '')
            if GEM_VOICE:    # Gemini reads plain text: no pinyin marks (say={} swaps a word it misreads), the direction goes in the style
                e = {'id': f"{sc['id']}.{c['k']}", 'text': text, 'tts_text': plain, 'voice': GEM_VOICE, 'style': style, 'base': base}
                cues.append(e); continue
            if VOLC_VOICE:   # no pinyin marks either (the 2.0 voices take no SSML); speed goes as a number
                e = {'id': f"{sc['id']}.{c['k']}", 'text': text, 'tts_text': plain, 'voice': VOLC_VOICE,
                     'style': style, 'rate': VOLC_RATE[c['rate']], 'base': base}
                cues.append(e); continue
            e = {'id': f"{sc['id']}.{c['k']}", 'text': text, 'tts_text': tts_text, 'dur': ITTS_DUR[c['rate']], 'base': base}
            if ev:
                e['emo'] = ev
            cues.append(e)
    json.dump(cues, open(os.path.join(BUILD, 'cues.json'), 'w'), ensure_ascii=False, indent=1)
    n = sum(1 for sc in SCENES for c in sc['cues'])
    chars = sum(1 for sc in SCENES for c in sc['cues'] for ch in c['t'] if ch not in PUNCT and ch != '|')
    print(len(cues), 'cues ->', os.path.join(BUILD, 'cues.json'), f'| {chars} chars')
    print(length_line()[0])



def script_hash():
    """Fingerprint of what gets voiced: every line, its pauses, rate and pronunciation marks. Change one character and it changes."""
    rows = [f"{sc['id']}.{c['k']}|{c['t']}|{c['rate']}|{sorted(c['py'].items())}" + (f"|{sorted(c['say'].items())}" if c.get('say') else '')
            for sc in SCENES for c in sc['cues']]
    return hashlib.sha256('\n'.join(rows).encode()).hexdigest()[:12]


def script_chars():
    return sum(1 for sc in SCENES for c in sc['cues'] for ch in c['t'] if ch not in PUNCT and ch != '|')


def quote_line():
    """Where the film's famous line (QUOTE) is first said, from the character count; the second value is True when it is
    missing or comes after 20 seconds."""
    if not QUOTE:
        return None, False
    norm = lambda x: ''.join(ch for ch in x if ch not in PUNCT and ch not in '|《》“”「」 ')
    q, done = norm(QUOTE), 0
    for sc in SCENES:
        for c in sc['cues']:
            t = norm(c['t']); i = t.find(q)
            if i >= 0:
                sec = (done + i) / CPS
                late = sec > 20
                return (f"名句「{QUOTE}」估计在第 {sec:.0f} 秒念到，" + ("晚于 20 秒：挪进开头。" if late else "在前 20 秒内。")), late
            done += len(t)
    return f"名句「{QUOTE}」稿子里没有原样念出来：用大家熟的说法，别改写。", True


def hook_line():
    """Where the opening line (HOOK) is finished, from the characters before and in it at the speaking rate; the second value
    is True when it is missing, not said word for word, or finished after 5 seconds."""
    if not HOOK:
        return "没写 HOOK：script.py 里写上开头那句（规格/各规格.md「开头」）。", True
    norm = lambda x: ''.join(ch for ch in x if ch not in PUNCT and ch not in '|《》“”「」 ')
    q, done = norm(HOOK), 0
    for sc in SCENES:
        for c in sc['cues']:
            t = norm(c['t']); i = t.find(q)
            if i >= 0:
                sec = (sc.get('lead', 0.3) if done == 0 else 0.3) + (done + i + len(q)) / HOOK_CPS
                late = sec > 5
                return (f"开头那句「{HOOK}」估计第 {sec:.1f} 秒念完，" + ("晚于 5 秒：砍短或挪到最前。" if late else "在前 5 秒内。")), late
            done += len(t)
    return f"开头那句「{HOOK}」稿子里没有原样念出来。", True


def mmss(t):
    return f"{int(t // 60)} 分 {int(round(t % 60)):02d} 秒"


def length_line():
    """One line on how long the script will run against the film's TARGET; the second value is True when it runs over."""
    est = script_chars() / CPS
    base = f"估计时长 {mmss(est)}（{script_chars()} 字 ÷ 每秒 {CPS} 字）"
    if not TARGET:
        return f"{base}，只做参考，不设上限。", False
    return f"{base}，任务书估的是 {mmss(TARGET)} 左右，只做参考：不为时长砍内容（规格/README.md）。", False


def review_sheet():
    """The script as the reviewer sees it: numbered lines, pauses shown as |, pronunciation marks listed."""
    out = []
    for sc in SCENES:
        out.append(f"\n## {sc['id']}" + (f" {sc['name']}" if sc.get('name') else ''))
        for c in sc['cues']:
            extra = ('  [拼音 ' + ' '.join(f'{k}={v}' for k, v in c['py'].items()) + ']') if c['py'] else ''
            extra += ('  [配音时送给 TTS 的字：' + '，'.join(f'{k}→{v}' for k, v in c['say'].items()) + '（钉读音，字幕不变）]') if c.get('say') else ''
            shown = '' if c['sub'] else '  [不出字幕，这句直接以画面文字出现]'
            out.append(f"{sc['id']}.{c['k']}  {c['t']}{extra}{shown}")
    print(f"稿子哈希：{script_hash()}")
    print(length_line()[0])
    if FILM:
        print(f"系列 {FILM.get('系列', '（没写）')}，规格 {SPEC}" + ('' if FEED else '：开头门禁只提示，不拦'))
    if quote_line()[0]:
        print(quote_line()[0])
    print(hook_line()[0])
    print('\n'.join(out))


def gate():
    """Voice only a script that passed review: 审稿.md must carry this script's hash and the verdict 过."""
    import re
    h = script_hash(); p = os.path.join(ROOT, '审稿.md')
    txt = open(p).read() if os.path.exists(p) else ''
    # only the two lines at the start of a line count; earlier rounds are written as 「哈希 …」「总结论：…」 below them
    m = re.search(r'^稿子哈希：\s*([0-9a-f]{12})', txt, re.M); v = re.search(r'^结论：\s*(\S)', txt, re.M)
    if not m or m.group(1) != h or not v or v.group(1) != '过':
        print(f"不配音：审稿.md {'不存在' if not txt else '没通过或已作废'}。当前稿子哈希 {h}，审稿里是 {m.group(1) if m else '无'}，结论 {v.group(1) if v else '无'}。先重审（python3 script.py sheet 给审稿人看）。")
        sys.exit(1)
    # 掏钱 (2026-10-08): talk it through as one piece first (口播稿.md), and a listener who gets only the script, no
    # background, must pass it too; the structure review alone let compressed, note-like lines through
    if not os.path.exists(os.path.join(ROOT, '口播稿.md')):
        print('不配音：视频文件夹里没有 口播稿.md。先像跟朋友一口气讲下来那样整段写，写完再对结构、切成句子（方法/稿子写给耳朵听.md）。')
        sys.exit(1)
    if not re.search(r'^听众审：\s*过', txt, re.M):
        print('不配音：审稿.md 顶上没有「听众审：过」。先交给只拿稿子、不给背景的审稿人听一遍（方法/两道审.md「听众审」）。')
        sys.exit(1)
    # the opening gates stop the voicing only in the feed's specs (规格/各规格.md); a documentary or a brand film is told
    hline, hbad = hook_line()
    if hbad and not HOOK_LATE_OK:
        if FEED:
            print(f"不配音：{hline}确实要晚，在 script.py 写 HOOK_LATE_OK = '理由'（出品人点头的）。")
            sys.exit(1)
        print(f"提示（{SPEC}不拦）：{hline}")
    qline, qbad = quote_line()
    if qbad and not QUOTE_LATE_OK:
        if FEED:
            print(f"不配音：{qline}确实要晚，在 script.py 写 QUOTE_LATE_OK = '理由'（出品人点头的）。")
            sys.exit(1)
        print(f"提示（{SPEC}不拦）：{qline}")
    line, _ = length_line()
    print(f'审稿通过，稿子哈希 {h}。{line}')



def tone_mark(py):
    """KONG4 -> kòng, XVAN2 -> xuán: how the pinned reading is written for a listener"""
    s, t = py[:-1].lower().replace('v', 'ü'), int(py[-1])
    if s[:1] in 'jqxy':
        s = s.replace('ü', 'u')
    if t == 5:
        return s
    marks = {'a': 'āáǎà', 'e': 'ēéěè', 'i': 'īíǐì', 'o': 'ōóǒò', 'u': 'ūúǔù', 'ü': 'ǖǘǚǜ'}
    i = s.find('a') if 'a' in s else s.find('e') if 'e' in s else s.find('o') if 'ou' in s else max(s.rfind(v) for v in 'iouü')
    return s[:i] + marks[s[i]][t - 1] + s[i + 1:]


def listen():
    """build/抽听.wav + build/抽听.txt: the lines Claude cannot check by ear, for a human to listen through in one go.
    Readback only sees characters, so a pinned polyphone read in the wrong tone goes unnoticed; the lines the
    last readback flagged (build/align.txt) are added too."""
    flagged = []
    extra = {}                      # build/抽听_加.txt: «id|what to listen for», lines Claude wants a human ear on as well;
    for name in ('抽听_加.txt', '复认.txt'):   # build/复认.txt: words that, cut out alone, were heard as something else (recheck)
        pe = os.path.join(BUILD, name)
        if os.path.exists(pe):
            for l in open(pe):
                if '|' in l:
                    k, v = l.strip().split('|', 1); extra[k] = extra[k] + '；' + v if k in extra else v
    p = os.path.join(BUILD, 'align.txt')
    if os.path.exists(p):
        last = [l for l in open(p) if l.startswith('BAD:')]
        flagged = [x for x in (last[-1][4:].strip().split(',') if last else []) if x]
    tone = '一二三四'
    b = blip(1320, .06); b = b.mean(0) if b.ndim > 1 else b
    gap, beep = np.zeros(int(.7 * SR), np.float32), (b * .25).astype(np.float32)
    parts, rows, seen = [], [], {}
    for sc in SCENES:
        for c in sc['cues']:
            cid = f"{sc['id']}.{c['k']}"
            if not c['py'] and not c.get('say') and cid not in flagged and cid not in extra:
                continue
            text = c['t'].replace('|', '')
            key = clip_base(text, c['rate'], c.get('emo'), c['py'], c.get('say'))[0]
            if key in seen and cid not in flagged:      # the same recording as an earlier line (a repeated main line): listen once
                rows[seen[key]] += f'（{cid} 用的是同一段录音）'
                continue
            seen[key] = len(rows)
            x, _ = synth(text, RATES[c['rate']], emo_vec(c), c['py'], c)
            what = '；'.join(f"「{ch}」读 {tone_mark(py)}" + (f'（第{tone[int(py[-1]) - 1]}声）' if py[-1] in '1234' else '（轻声）') for ch, py in c['py'].items())
            if cid in flagged:
                what = (what + '；' if what else '') + '回读有出入，听整句清不清楚'
            if cid in extra:
                what = (what + '；' if what else '') + extra[cid]
            rows.append(f"{len(rows) + 1:2d}. {cid:11s} {text}    听：{what}")
            parts += [beep, np.zeros(int(.25 * SR), np.float32), x.astype(np.float32), gap]
    if not rows:
        print('没有要抽听的句子'); return
    y = np.concatenate(parts); y = y / max(1e-6, np.abs(y).max()) * .89
    with wave.open(os.path.join(BUILD, '抽听.wav'), 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
    head = f"抽听：{len(rows)} 句，约 {len(y) / SR:.0f} 秒（build/抽听.wav）。每句前有一声提示音。回读只认字、听不出声调，这几句要靠人耳。"
    open(os.path.join(BUILD, '抽听.txt'), 'w').write(head + '\n' + '\n'.join(rows) + '\n')
    print(head); print('\n'.join(rows))


def qc_times():
    """Every line at its middle and near its end, plus the middle of each transition."""
    tl = json.load(open(os.path.join(ROOT, 'timeline.json')))
    ts = []
    for s in tl['scenes']:
        for c in s['cues']:
            for f in (.5, .92):
                ts.append(round(s['start'] + c['start'] + (c['end'] - c['start']) * f, 2))
        if s.get('out'):
            ts.append(round(s['out'] + TRANS[s['trans']] / 2, 2))
    print(','.join(map(str, ts)))


def ebur128(path):
    """Loudness of a file by ffmpeg's ebur128: integrated (LUFS) and the momentary loudness (400 ms) every 0.1 s."""
    import re
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=framelog=info', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    rows = [(float(t), float(m)) for t, m in re.findall(r't:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)', out) if m != '-inf']
    I = re.findall(r'I:\s*(-?[\d.]+|-inf) LUFS', out)
    return (float(I[-1]) if I and I[-1] != '-inf' else -70.0), rows


def write_mix(total, stems=None, talk=None, peak=0.89):
    """build/audio.wav from the summed mix, scaled so its peak sits at `peak`. Give it the stems ({'voice': ..., 'music': ...,
    'fx': ...}, each shaped like total) and the talk mask (1 where a line is being said, one value per sample): each stem is
    written with the same gain to build/stem_<name>.wav and measured in loudness units (ffmpeg ebur128), so the music level
    is set by how loud it sounds, not by RMS: K-weighting hears the voice's middle and top more than the music's low end
    (大理, 2026-10-17: by RMS the music sat 10.7 dB under the voice, by loudness 12.6 LU — a little light). MUSG is set by
    the LU figures this prints."""
    g = 1.0 / max(1e-9, np.abs(total).max() / peak)
    def wr(path, x):
        with wave.open(path, 'w') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(x * g, -1, 1).T * 32767).astype(np.int16).tobytes())
    wr(os.path.join(BUILD, 'audio.wav'), total)
    for name, x in (stems or {}).items():
        wr(os.path.join(BUILD, f'stem_{name}.wav'), x)
    if stems and 'voice' in stems and 'music' in stems:
        mix_lu(talk)


HOLES = []    # the default mix(): cue refs ('main.m0') the music steps back under, so a key line lands in near-silence
MUSG = None   # the default mix()'s music gain; None = $MUSG or 1.35
# the default mix()'s other knobs, from 运动 (2026-10-18); a film that leaves them alone mixes as before
MUSIC_SEAMS = None   # where one track hands over to the next. None: in the pauses nearest equal shares of the film.
                     # 'chapters': at the scene changes, 0.2 s before each transition starts (no words there, the hand-over
                     # is heard in the open), one track per scene in order, the scenes past the last track riding on it;
                     # or the ids of the scenes a new track comes in for (['grow', 'aero', 'lift']). Set either way, the
                     # silence Lyria often leaves at a track's start is skipped (运动: a chapter change fell to -59 dB) and
                     # the tracks cross wider (the old one runs 2.4 s on and fades over 2.6 s, the new one fades in over 1.2 s)
DUCK = 0.75          # how far the music steps back while a line is said (运动: 0.65 with MUSG 1.0)
DIPS = []            # cue refs the music sits about 3 dB lower under: mixcheck heard the line covered (运动: a7, r2)
CARD_LIFT = {}       # {scene id: gain}: the music under the chapter card that leads into that scene, where the track runs
                     # thin and the first words jump out of it (运动: {'aero': 1.41}, about +3 dB)


def music_set():
    """The music set in use: music/选用.txt after the blind listen (one letter for the film, or one per stretch), else the
    片子.json 配乐套, else A."""
    p = os.path.join(ROOT, 'music', '选用.txt')
    sel = open(p).read().split() if os.path.exists(p) else []
    return sel or [FILM.get('配乐套', 'A')]


def mix():
    """The plain mix a film starts from, until it has sounds of its own (多问一层's mix() is the full kind; a film writes its
    own mix() and this one is gone). The voice levelled, with a touch of room; the tracks of the music set (music/<set><n>.mp3,
    n = 1, 2, ...) one after another, the seams in the pauses nearest equal shares of the film (MUSIC_SEAMS = 'chapters':
    in the scene changes), the last one ending on its own ending; ducked under the voice (DUCK) and a little more as lines
    trail off, a quarter under the HOLES, a little under the DIPS, raised under a CARD_LIFT chapter card; then write_mix,
    which prints the levels in LU."""
    import glob, re
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    tl = json.load(open(os.path.join(ROOT, 'timeline.json')))
    D = tl['duration'] + 0.3
    N = int(D * SR)
    voice, music = np.zeros((2, N)), np.zeros((2, N))
    mask, spans = np.zeros(N), []
    room_ir = reverb_ir(0.5, 9, 3500)[0]
    for s_ in tl['scenes']:
        for c in s_['cues']:
            x = np.load(c['clip']).astype(np.float64)
            act = np.abs(x) > 0.01
            if act.any():
                x = np.tanh(x * (0.13 / np.sqrt(np.mean(x[act] ** 2))) * 1.2) / 1.2
            wet = signal.fftconvolve(x, room_ir)[:len(x) + int(0.35 * SR)] * 0.05
            add(voice, np.concatenate([x, np.zeros(len(wet) - len(x))]) + wet, c['abs'], 1.0)
            mask[int(c['abs'] * SR):int((c['abs'] + len(x) / SR) * SR)] = 1
            spans.append((c['abs'], c['abs'] + len(x) / SR, f"{s_['id']}.{c['k']}"))

    def track(src, need):
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
                                   capture_output=True, text=True).stdout or 0)
        af = ['-af', f'atempo={max(.85, dur / need):.4f}'] if 0 < dur < need else []
        raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', src, *af, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                             capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.float32).reshape(-1, 2).T.astype(np.float64)

    sel = music_set()
    nums = sorted({int(m.group(1)) for f in glob.glob(os.path.join(ROOT, 'music', '*.mp3'))
                   for m in [re.match(r'[A-Z](\d+)\.mp3$', os.path.basename(f))] if m})
    sc, cuts = tl['scenes'], []
    if not nums:
        print('没有配乐：music/ 里还没有 A1.mp3 这样的曲子（./make.sh music 生成），先只混人声。')
    else:
        n = len(nums)
        sel = (sel * n)[:n] if len(sel) == 1 else sel
        if MUSIC_SEAMS:
            # in the scene changes, 0.2 s before the transition into each scene named starts: nobody speaks in a transition,
            # so the hand-over is heard in the open (运动: seven tracks, the paper rolling past at every chapter)
            ids = [s_['id'] for s_ in sc[1:]]
            want = ids if MUSIC_SEAMS == 'chapters' else list(MUSIC_SEAMS)
            for r in want:
                if r not in ids:
                    print(f'MUSIC_SEAMS 里的 {r} 不是时间轴上换进来的一场（第一场不算）')
            cuts = [(sc[i]['id'], sc[i - 1]['out'] - 0.2) for i in range(1, len(sc)) if sc[i]['id'] in want]
            if len(cuts) > n - 1:
                print(f"配乐只有 {n} 段：换进 {'、'.join(r for r, _ in cuts[n - 1:])} 时不换曲子，接着用第 {n} 段")
            elif len(cuts) < n - 1:
                print(f'配乐有 {n} 段，换场只有 {len(cuts)} 处：后 {n - 1 - len(cuts)} 段没用上')
            cuts = cuts[:n - 1]
            seams = [0.0] + [t for _, t in cuts] + [D]
            n = len(seams) - 1
        else:
            gaps = [((b1 + a2) / 2, a2 - b1) for (a1, b1, _), (a2, b2, _) in zip(spans, spans[1:])]
            seams = [0.0]
            for i in range(1, n):
                cand = [m for m, g in gaps if g > .25 and m > seams[-1] + 8]
                seams.append(min(cand, key=lambda m: abs(m - D * i / n)) if cand else D * i / n)
            seams.append(D)
        wide = bool(MUSIC_SEAMS)
        for k in range(n):
            last = k == n - 1
            L = seams[k + 1] - seams[k] + (0.0 if last else 2.4 if wide else 1.6)
            y = track(os.path.join(ROOT, 'music', f'{sel[k]}{nums[k]}.mp3'), L + 2.5)
            lead = 0
            if wide:   # Lyria often leaves a second or two of silence at the start: come in 0.12 s before the track gets going
                en = np.sqrt(uniform_filter1d((y ** 2).mean(0), size=int(.05 * SR)) + 1e-12)
                lead = max(0, int(np.argmax(en > .45 * (np.sqrt(np.mean(y ** 2)) + 1e-9))) - int(.12 * SR))
            off = max(0.0, (y.shape[1] - lead) / SR - L - 0.5) if last else 0.0      # the last one lined up near its own ending
            a0 = lead + int(off * SR)
            seg = y[:, a0:a0 + int(L * SR)]
            while 0 < seg.shape[1] < int(L * SR):
                seg = np.concatenate([seg, y[:, :int(L * SR) - seg.shape[1]]], axis=1)
            if not seg.shape[1]:
                continue
            e = np.ones(seg.shape[1])
            fi, fo = int((0.15 if k == 0 else 1.2 if wide else 1.6) * SR), int((0.5 if last else 2.6 if wide else 2.0) * SR)
            e[:fi] = np.linspace(0, 1, fi) ** 1.5; e[-fo:] *= np.linspace(1, 0, fo) ** 1.5
            rms = np.sqrt(np.mean(seg ** 2)) + 1e-9
            env = np.sqrt(uniform_filter1d((seg ** 2).mean(0), size=int(3 * SR)) + 1e-12)
            seg = seg * np.clip((rms / env) ** .6, .55, 1.4)                   # even out the track's own swells
            add(music, seg * e * (0.095 / rms), seams[k], 1.0)
    held = maximum_filter1d(mask, size=int(0.3 * SR))
    sm = np.clip(uniform_filter1d(held, size=int(0.3 * SR)), 0, 1)
    tails, holes = np.zeros(N), np.zeros(N)
    for a, b, _ in spans:                       # line endings trail off: dip the music a little more there
        tails[int(max(0, b - .8) * SR):int((b + .1) * SR)] = 1
    byref = {r: (a, b) for a, b, r in spans}
    for r in HOLES:
        if r not in byref:
            print(f'HOLES 里的 {r} 不在时间轴上')
            continue
        a, b = byref[r]
        holes[int(max(0, a - .2) * SR):int((b + .5) * SR)] = 1
    tails, holes = uniform_filter1d(tails, size=int(.25 * SR)), uniform_filter1d(holes, size=int(.5 * SR))
    g = MUSG if MUSG is not None else float(os.environ.get('MUSG', 1.35))
    mus = music * (1 - DUCK * sm) * (1 - .25 * tails) * (1 - .75 * holes)
    if DIPS:
        dips = np.zeros(N)
        for r in DIPS:
            if r not in byref:
                print(f'DIPS 里的 {r} 不在时间轴上')
                continue
            a, b = byref[r]
            dips[int(max(0, a - .2) * SR):int((b + .3) * SR)] = 1
        mus = mus * (1 - .3 * uniform_filter1d(dips, size=int(.5 * SR)))
    for r, lift in CARD_LIFT.items():   # from the start of the transition into scene r to just after the scene begins
        i = next((i for i, s_ in enumerate(sc) if s_['id'] == r and i), None)
        if i is None:
            print(f'CARD_LIFT 里的 {r} 不是时间轴上换进来的一场（第一场不算）')
            continue
        card = np.zeros(N)
        card[int(sc[i - 1]['out'] * SR):int((sc[i]['start'] + .3) * SR)] = 1
        mus = mus * (1 + (lift - 1) * uniform_filter1d(card, size=int(.6 * SR)))
    mus = mus * g
    total = voice + mus + noise_bed(D, 3, 600)[:, :N] * 0.005
    fade = int(1.6 * SR)
    total[:, -fade:] *= np.linspace(1, 0, fade) ** 2
    write_mix(total, {'voice': voice, 'music': mus}, mask)
    db = lambda a: 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-12)
    v, m = voice.mean(0), mus.mean(0)
    print(f"audio ok {N / SR:.1f}s | 按 RMS：voice {db(v[mask > 0]):.1f} dB, music under voice {db(m[mask > 0]):.1f}, in pauses {db(m[mask == 0]):.1f}（调 MUSG 看上面那行 LU）")
    if cuts:
        print('配乐接缝：' + '，'.join(f'{t:.1f} 秒进 {r}（{sel[k + 1]}{nums[k + 1]}）' for k, (r, t) in enumerate(cuts)))


def mix_lu(talk=None):
    """How far the music sits under the voice, in LU, from build/stem_voice.wav and build/stem_music.wav: over the whole
    film (integrated), while a line is being said and in the pauses (momentary loudness, energy-averaged; a 400 ms window
    counts as talk when a line fills 80% of it, as a pause when no line touches it). The voice's reference is its own
    level while talking."""
    iv, mv = ebur128(os.path.join(BUILD, 'stem_voice.wav'))
    im, mm = ebur128(os.path.join(BUILD, 'stem_music.wav'))
    if iv <= -69 or im <= -69:
        print(f"响度（LUFS）：{'人声轨' if iv <= -69 else '配乐轨'}是静音（时间轴是估计的，或者还没有配乐），没法比")
        return ''
    line = f'响度（LUFS）：人声 {iv:.1f}，配乐 {im:.1f}，整片配乐比人声低 {iv - im:.1f} LU'
    if talk is not None and len(mv) and len(mm):
        cum = np.concatenate([[0], np.cumsum(talk > 0)])
        frac = lambda t: (cum[min(len(talk), int(t * SR))] - cum[max(0, int((t - .4) * SR))]) / (.4 * SR)
        avg = lambda xs: 10 * math.log10(np.mean([10 ** (x / 10) for x in xs])) if xs else float('nan')
        M = dict(mm)
        tv = [m for t, m in mv if frac(t) >= .8]
        tm = [M[t] for t, m in mv if frac(t) >= .8 and t in M]
        pm = [M[t] for t, m in mv if frac(t) <= 0 and t in M and 1 < t < (len(talk) / SR) - 6]
        lv = avg(tv)
        line += f'；说话时低 {lv - avg(tm):.1f} LU，停顿时低 {lv - avg(pm):.1f} LU（停顿时比说话时的人声）'
    print(line)
    return line


def qc_loudness():
    """Short-term loudness of the finished file: where it jumps between neighbouring seconds."""
    import glob, re
    f = sys.argv[2] if len(sys.argv) > 2 else max(glob.glob((OUT_DIR + f'/*--{os.path.basename(ROOT)[8:]}*__video.mp4')), key=os.path.getmtime)   # the newest cut, versions included
    # framelog=info: ffmpeg 8 prints the per-frame lines only at info level; with verbose nothing matched and the report
    # fell back to a made-up -20 LUFS and 0 jumps for every film up to 一口气 (2026-10-13)
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128=framelog=info', '-f', 'null', '-'], capture_output=True, text=True).stderr
    rows = [(float(a), float(m), float(s_)) for a, m, s_ in re.findall(r't:\s*([\d.]+)\s+TARGET:.*?M:\s*([-\d.]+)\s+S:\s*([-\d.]+)', out)]
    if not rows:
        print(f'文件 {os.path.basename(f)}')
        print('没读到响度数据（ffmpeg 输出格式变了？）')
        return
    end = rows[-1][0]
    S = {round(t, 1): s_ for t, m, s_ in rows}
    M = [(t, m) for t, m, s_ in rows]
    speech = sorted(s_ for _, _, s_ in rows if s_ > -40)
    med = speech[len(speech) // 2] if speech else -20
    jumps = []
    for t, s_ in S.items():
        if t > end - 5:
            continue   # the end card fades out: every film jumps there, not worth reporting
        s2 = S.get(round(t + 1.0, 1))
        if s2 is not None and s_ > -40 and s2 > -40 and abs(s2 - s_) > 5:
            jumps.append((abs(s2 - s_), t, s_, s2))
    jumps.sort(reverse=True)
    spikes = [(t, m) for t, m in M if m > med + 9]
    print(f'文件 {os.path.basename(f)}')
    print(f'短时响度中位数 {med:.1f} LUFS；相邻一秒跳变超过 5 LU 的 {len(jumps)} 处；瞬时响度高出中位数 9 LU 以上的 {len(spikes)} 帧')
    for d, t, a, b in jumps[:12]:
        print(f'  {t:6.1f}s  {a:6.1f} → {b:6.1f}  (跳 {d:.1f} LU)')
    last = -9
    for t, m in spikes:
        if t - last > 1.0:
            print(f'  尖峰 {t:6.1f}s  M {m:.1f}')
        last = t


def trial():
    """./make.sh try h1,b3,c4,g5: the same lines read with GEM_BASE and with GEM_STRICT, for a blind listen.
    Which direction plays first (A) is drawn at random and written to build/试音/答案.txt. Every take is saved where
    the voice step looks for it, so the direction that wins keeps its takes. build/试音/cues.json lets align read them back."""
    import random
    if not GEM_VOICE:
        sys.exit('try 只比 Gemini 的两种语气指示；火山的音色盲听用 voices/火山试音/做试音.py')
    byk = {c['k']: c for sc in SCENES for c in sc['cues']}
    ids = sys.argv[2].split(',')
    dirs = {'自然（GEM_BASE）': GEM_BASE, '严格逐字（GEM_STRICT）': GEM_STRICT}
    names = list(dirs); random.shuffle(names)
    out = os.path.join(BUILD, '试音'); os.makedirs(out, exist_ok=True)
    b = blip(1320, .06).mean(0) * .25
    gap = np.zeros(int(.8 * SR)); parts, cues = [], []
    for k in ids:
        c = byk[k]; text = c['t'].replace('|', '')
        for j, nm in enumerate(names):
            style = dirs[nm] + GEM_RATE.get(c['rate'], '') + (GEM_EMO.get(c['emo'], '') if (EMO_ON and c.get('emo')) else '')
            base = os.path.join(BUILD, 'gemini', GEM_VOICE, 'gem_' + hashlib.md5(f'gemini|{GEM_VOICE}|{style}|{text}'.encode()).hexdigest()[:12])
            os.makedirs(os.path.dirname(base), exist_ok=True)
            if not os.path.exists(base + '.wav'):
                subprocess.run([sys.executable, os.path.join(ROOT, '..', '..', 'engines', 'gemini.py'), 'say', base + '.wav', GEM_VOICE, style,
                                text.replace('“', '').replace('”', '')], check=True)
            sr, x = load_wav(base + '.wav')
            x = signal.resample_poly(x, SR, sr) if sr != SR else x
            for _ in range(j + 1):                     # one beep before A, two before B
                parts += [b, np.zeros(int(.12 * SR))]
            parts += [np.zeros(int(.2 * SR)), x, gap]
            cues.append({'id': f"{k}.{'AB'[j]}", 'text': text, 'base': base})
    y = np.concatenate(parts); y = y / max(1e-6, np.abs(y).max()) * .89
    with wave.open(os.path.join(out, '试音.wav'), 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
    json.dump(cues, open(os.path.join(out, 'cues.json'), 'w'), ensure_ascii=False, indent=1)
    open(os.path.join(out, '答案.txt'), 'w').write(f'A = {names[0]}\nB = {names[1]}\n')
    open(os.path.join(out, '试音.txt'), 'w').write(
        f"试音：{len(ids)} 句，每句先 A（一声提示音）后 B（两声），约 {len(y) / SR:.0f} 秒（build/试音/试音.wav）。\n"
        "两种语气指示，挑听着更自然、又不乱加字的那一个。答案在 答案.txt，听完再看。\n" +
        '\n'.join(f"{i + 1}. {byk[k]['t'].replace('|', '')}" for i, k in enumerate(ids)) + '\n')
    print(f'试音 {len(y) / SR:.0f}s -> {out}/试音.wav')


def music_trial():
    """./make.sh musictry open.h0-o4c,L4.d1-d5,L6.f6-f10 [A B]: a blind listen of the music sets under the voice. Each set is
    mixed in full (music/选用.txt set to it for the run, put back after), the same stretches are cut from every mix and
    played set after set in a random order: 甲 (one beep), 乙 (two)… The answer is in build/配乐试听/答案.txt. Pure music
    cannot tell whether it fits the words and their pace (掏钱 v2: the pick was made by listening to three stretches with the voice).
    build/audio.wav is left as the last set's mix: run ./make.sh mix once the pick is in."""
    import random
    spans = sys.argv[2].split(','); sets = sys.argv[3:] or ['A', 'B']
    pick = os.path.join(ROOT, 'music', '选用.txt'); keep = open(pick).read() if os.path.exists(pick) else None
    mixes = {}
    try:
        for g in sets:
            open(pick, 'w').write(g + '\n'); mix()
            with wave.open(os.path.join(BUILD, 'audio.wav')) as w:
                sr = w.getframerate(); mixes[g] = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, w.getnchannels()).astype(np.float32) / 32768
    finally:
        if keep is None: os.remove(pick)
        else: open(pick, 'w').write(keep)
    tl = json.load(open(os.path.join(ROOT, 'timeline.json'))); sc = {s['id']: s for s in tl['scenes']}
    def at(ref, end):
        sid, k = ref.split('.'); c = next(c for c in sc[sid]['cues'] if c['k'] == k)
        return sc[sid]['start'] + (c['end'] if end else c['start'])
    order = list(sets); random.shuffle(order); labels = '甲乙丙丁戊'
    def beep(n):
        t = np.arange(int(.08 * sr)) / sr; b = (np.sin(2 * np.pi * 1320 * t) * .25).astype(np.float32)
        return np.concatenate([np.concatenate([b, np.zeros(int(.12 * sr), np.float32)]) for _ in range(n)])
    seq, rows = [], []
    for i, span in enumerate(spans):
        a, b = span.split('-'); sid = a.split('.')[0]
        t1 = max(0.0, at(a, False) - 1.0); t2 = at(f'{sid}.{b}' if '.' not in b else b, True) + 1.5
        for j, g in enumerate(order):
            x = mixes[g][int(t1 * sr):int(t2 * sr)].copy(); f = int(.3 * sr)
            x[:f] *= np.linspace(0, 1, f)[:, None]; x[-f:] *= np.linspace(1, 0, f)[:, None]
            seq += [np.repeat(beep(j + 1)[:, None], 2, 1), np.zeros((int(.3 * sr), 2), np.float32), x, np.zeros((sr, 2), np.float32)]
        rows.append(f'{i + 1}. {span}（{t2 - t1:.0f} 秒）')
    y = np.concatenate(seq); y = y / max(1e-6, np.abs(y).max()) * .95
    out = os.path.join(BUILD, '配乐试听'); os.makedirs(out, exist_ok=True)
    with wave.open(os.path.join(out, '配乐试听.wav'), 'w') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype(np.int16).tobytes())
    open(os.path.join(out, '答案.txt'), 'w').write(''.join(f'{labels[j]} = {g}\n' for j, g in enumerate(order)))
    open(os.path.join(out, '试听.txt'), 'w').write(f"配乐盲听：{len(spans)} 段，每段按 {'、'.join(labels[:len(order)])} 的顺序各放一遍（提示音一声、两声…），约 {len(y) / sr:.0f} 秒。答案在 答案.txt，听完再看。\n" + '\n'.join(rows) + '\n')
    print(f'配乐试听 {len(y) / sr:.0f}s -> {out}/配乐试听.wav；选定后写进 music/选用.txt，再跑 ./make.sh mix')


def load_events(path=None):
    """build/events.json (./make.sh events: the film's EV.build() list, lib/events.js). Refuses a list exported from another
    timeline: re-voicing or a script change moves every word, and the sound would land where the old picture was."""
    p = path or os.path.join(BUILD, 'events.json')
    if not os.path.exists(p):
        sys.exit('build/events.json 不在：先跑 ./make.sh events（render.js 里用 EV.build 定下事件表）')
    ev = json.load(open(p, encoding='utf-8'))
    sha = hashlib.sha256(open(os.path.join(ROOT, 'timeline.json'), 'rb').read()).hexdigest()
    if ev.get('meta', {}).get('timeline_sha256') != sha:
        sys.exit('build/events.json 是旧时间轴导出的（时间轴改过）：重跑 ./make.sh events 再混音')
    return ev['events']


def attack_offset(clip, frac=0.3):
    """Seconds from a sample's start to its attack (the first 1 ms step where a 5 ms RMS envelope reaches frac of its peak):
    a whoosh that swells for 0.3 s placed at t is heard 0.3 s late."""
    x = np.abs(clip).mean(0) if clip.ndim == 2 else np.abs(clip)
    win, hop = max(1, int(.005 * SR)), max(1, int(.001 * SR))
    env = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, 'same')[::hop])
    if not len(env) or env.max() <= 0:
        return 0.0
    return float(np.argmax(env >= frac * env.max()) * hop / SR)


def fx_from_events(buf, sfx=None, events=None):
    """Every event with an 'sfx' placed in buf (shaped like the mix) at its time minus the sample's attack offset, at its
    gain. sfx: {name: fn} to look the names up in (default: the functions of sound.py and the film's script.py). Returns the
    events placed, for the film's own bookkeeping (方法/声音.md「声音上的贴」)."""
    events = load_events() if events is None else events
    look, cache, placed = sfx or globals(), {}, []
    for e in events:
        name = e.get('sfx')
        if not name:
            continue
        if not callable(look.get(name)):
            sys.exit(f"事件 {e.get('id')} 的音效 {name} 在 sound.py / script.py 里没有")
        key = (name, json.dumps(e.get('args', {}), sort_keys=True))
        if key not in cache:
            clip = np.asarray(look[name](**e.get('args', {})), dtype=np.float64)
            cache[key] = (clip, attack_offset(clip))
        clip, pre = cache[key]
        if e.get('pan'):
            c = clip if clip.ndim == 2 else np.stack([clip, clip])
            p_ = float(e['pan']); clip = c * np.array([[min(1, 1 - p_)], [min(1, 1 + p_)]])
        add(buf, clip, e['t'] - pre, e.get('gain', 0.5))
        placed.append(e)
    print(f'事件音效 {len(placed)} 个（按起音对齐：放在 t 减去样本自己的起音偏移）')
    return placed


def main():
    {'tts': tts, 'mix': mix, 'export': export, 'hash': lambda: print(script_hash()), 'sheet': review_sheet, 'gate': gate, 'qctimes': qc_times, 'listen': listen, 'loudness': qc_loudness, 'try': trial, 'musictry': music_trial, 'mixlu': mix_lu, 'subcheck': subskip_check}[sys.argv[1]]()
