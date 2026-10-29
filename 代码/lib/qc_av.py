"""The finished file: black frames and silences that are not meant to be there. Transitions go dark on purpose, and so do
the first second and the last two; anything else is reported (a missing scene, a music track that ends too early).
Run from a film's folder (make.sh qc does): python3 ../../lib/qc_av.py [file]   (default: the newest cut in ~/Documents/notes)"""
import glob, json, os, re, subprocess, sys
OUT_DIR = __import__("os").environ.get("OUT_DIR") or __import__("os").path.expanduser("~/Documents/notes")   # where finished films go (make.sh mux)

here = os.getcwd()
f = sys.argv[1] if len(sys.argv) > 1 else max(glob.glob((OUT_DIR + f'/*--{os.path.basename(here)[8:]}*__video.mp4')), key=os.path.getmtime)
tl = json.load(open('timeline.json')); D = tl['duration']
meant = [(0, 1.0), (D - 2.0, D + 5)] + [(s['out'] - .2, s['out'] + tl['trans'][s['trans']] + .2) for s in tl['scenes'] if s.get('out')]
inside = lambda a, b: any(a >= x0 and b <= x1 for x0, x1 in meant)
err = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-vf', 'blackdetect=d=0.3:pic_th=0.97:pix_th=0.10',
                      '-af', 'silencedetect=n=-50dB:d=0.8', '-f', 'null', '-'], capture_output=True, text=True).stderr
black = [(float(a), float(b)) for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', err)]
starts = [float(x) for x in re.findall(r'silence_start: (-?[\d.]+)', err)]
ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', err)] + [D]
quiet = list(zip(starts, ends))
bad_black = [(a, b) for a, b in black if not inside(a, b)]
bad_quiet = [(a, b) for a, b in quiet if not inside(max(0, a), b)]
print(f'文件 {os.path.basename(f)}')
print(f'黑屏超过 0.3 秒（转场和首尾以外）：{len(bad_black)} 处')
for a, b in bad_black: print(f'  {a:6.1f}–{b:6.1f}s')
print(f'静音超过 0.8 秒（转场和首尾以外）：{len(bad_quiet)} 处')
for a, b in bad_quiet: print(f'  {max(0, a):6.1f}–{b:6.1f}s')
