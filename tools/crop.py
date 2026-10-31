import sys
from PIL import Image

im = Image.open(sys.argv[1])
x0, y0, x1, y1 = (int(v) for v in sys.argv[2:6])
scale = int(sys.argv[6]) if len(sys.argv) > 6 else 3
c = im.crop((x0, y0, x1, y1))
c = c.resize((c.width * scale, c.height * scale), Image.NEAREST)
out = sys.argv[7] if len(sys.argv) > 7 else "/tmp/crop.png"
c.save(out)
print(out, c.size)
