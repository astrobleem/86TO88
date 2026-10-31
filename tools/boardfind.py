import sys
from PIL import Image
import numpy as np

im = Image.open(sys.argv[1]).convert("L")
a = np.asarray(im, dtype=np.int16)
H, W = a.shape
# edge strength: horizontal gradient summed over rows in band, vertical over cols
band_y = slice(330, 560)
gx = np.abs(np.diff(a[band_y, :], axis=1)).sum(axis=0)
# find strong periodic vertical lines in x 150..500
xs = [(x, gx[x]) for x in range(150, 500)]
xs.sort(key=lambda t: -t[1])
print("top vertical edges x:", [x for x, _ in xs[:12]])
band_x = slice(170, 470)
gy = np.abs(np.diff(a[:, band_x], axis=0)).sum(axis=1)
ys = [(y, gy[y]) for y in range(320, 600)]
ys.sort(key=lambda t: -t[1])
print("top horizontal edges y:", [y for y, _ in ys[:12]])
