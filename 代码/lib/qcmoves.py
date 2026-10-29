"""Where the picture moves a lot: the camera moving, a scene sliding away, a big card flying up. The frames the checks
look at sit on the lines (each at its middle and near its end) and on chapter transitions, so a camera move between two
lines can go unseen: in one film the protagonist showed up twice while the camera went through the door, and a card
slid under the subtitles while the camera tilted up from the floor; neither was on a frame until a reviewer asked.
Reads the cut, writes build/qc_moves.json ([[start, end], ...] in seconds); `qcpoints.py moves` adds frames inside each
window (one for a short one, three for a long one). Run from a film's folder (make.sh qc does):
  python3 ../../lib/qcmoves.py <cut.mp4>"""
import json, subprocess, sys
import numpy as np

# the share of the picture that changed between two frames 0.2 s apart; in one film ordinary animation (carts
# moving, slips flying, a person busy at a stall) stayed under 0.21 and every camera move went over 0.4
W, H, FPS, THR = 108, 192, 5, .25
raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', sys.argv[1], '-vf', f'fps={FPS},scale={W}:{H},format=gray',
                      '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.int16)
moved = (np.abs(np.diff(fr, axis=0)) > 12).mean(axis=(1, 2))
wins = []
for i in np.where(moved > THR)[0]:
    if wins and i - wins[-1][1] <= 2: wins[-1][1] = i   # gaps under 0.4 s join up
    else: wins.append([i, i])
end = len(fr) / FPS
wins = [[round(a / FPS, 2), round((b + 1) / FPS, 2)] for a, b in wins]
wins = [w for w in wins if w[0] > .3 and w[1] < end - 2]   # not the first frame, not the closing fade
json.dump(wins, open('build/qc_moves.json', 'w'))
print(f'画面大动的地方（镜头在移、大块东西进出）：{len(wins)} 段，qc 在每段里加帧（短的一帧，长的三帧）')
