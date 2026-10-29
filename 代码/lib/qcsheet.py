"""Phone-size contact sheets for the second review: 20 frames a sheet (5 x 4, 1080 x 1536, small enough for a reviewer to
read one at a time) and an index saying which line or transition each frame is. Run from a film's folder once the stills
exist (make.sh qc does): python3 ../../lib/qcsheet.py build/qc_points.json"""
import json, sys
from PIL import Image

pts = json.load(open(sys.argv[1]))
name = lambda t: str(int(t)) if float(t) == int(t) else str(t)
ims = [Image.open(f'build/still_{name(t)}.png').resize((216, 384)) for t, _ in pts]
per, cols = 20, 5
for k in range(0, len(ims), per):
    part = ims[k:k + per]; rows = (len(part) + cols - 1) // cols
    sheet = Image.new('RGB', (216 * cols, 384 * rows), (24, 24, 24))
    for i, im in enumerate(part): sheet.paste(im, ((i % cols) * 216, (i // cols) * 384))
    sheet.save(f'build/qc_sheet_{k // per + 1}.jpg', quality=90)
with open('build/qc_index.txt', 'w') as f:
    f.write(f'联系表格子索引：每张 {per} 格，每行 {cols} 格，从左到右、从上到下编号。每个转场有三格：过了四分之一、一半、四分之三；画面大动的地方（镜头在移、大块东西进出）短的一格、长的三格。\n')
    for i, (t, w) in enumerate(pts): f.write(f'表{i // per + 1} 格{i % per + 1:02d}  {float(t):7.2f}s  {w}\n')
n = (len(ims) + per - 1) // per
print(f'手机尺寸联系表：build/qc_sheet_1.jpg 到 build/qc_sheet_{n}.jpg（{len(ims)} 格），格子索引 build/qc_index.txt')
