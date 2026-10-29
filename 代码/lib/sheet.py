import sys, json
from PIL import Image
# usage: python3 sheet.py out.png t1 t2 ...   (stills must exist in build/)
out, ts = sys.argv[1], sys.argv[2:]
def name(t):
    f = float(t); return str(int(f)) if f == int(f) else t
ims = [Image.open(f'build/still_{name(t)}.png').resize((270, 480)) for t in ts]
cols = 6; rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (270 * cols, 480 * rows), (30, 30, 30))
for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * 270, (i // cols) * 480))
sheet.save(out)
