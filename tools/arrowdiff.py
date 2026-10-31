import sys
from PIL import Image
import numpy as np

a = np.asarray(Image.open(sys.argv[1]).convert("L"), dtype=np.int16)
b = np.asarray(Image.open(sys.argv[2]).convert("L"), dtype=np.int16)
d = (np.abs(a - b) > 40)
ys, xs = np.nonzero(d)
print("changed px:", len(xs))
if len(xs) == 0:
    sys.exit()
# cluster by grid cells of 24px
cells = {}
for x, y in zip(xs, ys):
    k = (x // 24, y // 24)
    cells.setdefault(k, []).append((x, y))
# merge adjacent cells (8-neighborhood over cell keys)
keys = list(cells)
parent = {k: k for k in keys}
def find(k):
    while parent[k] != k:
        parent[k] = parent[parent[k]]; k = parent[k]
    return k
for k in keys:
    for dk in [(1,0),(0,1),(1,1),(1,-1)]:
        n = (k[0]+dk[0], k[1]+dk[1])
        if n in parent:
            parent[find(n)] = find(k)
groups = {}
for k in keys:
    groups.setdefault(find(k), []).extend(cells[k])
out = []
for pts in groups.values():
    px = [p[0] for p in pts]; py = [p[1] for p in pts]
    out.append((len(pts), min(px), min(py), max(px), max(py),
                sum(px)/len(px), sum(py)/len(py)))
out.sort(reverse=True)
for n, x0, y0, x1, y1, cx, cy in out[:8]:
    print(f"cluster n={n} bbox=({x0},{y0})-({x1},{y1}) centroid=({cx:.0f},{cy:.0f})")
