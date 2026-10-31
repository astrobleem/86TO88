import sys
from PIL import Image
import numpy as np

# Board geometry in screenshot file pixels (1280x756 screencapture region).
X0, Y0, CELL = 181, 323, 32

def classify(a, r, c):
    x0, y0 = X0 + c * CELL, Y0 + r * CELL
    cell = a[y0:y0 + CELL, x0:x0 + CELL].astype(int)
    # bevel test: covered cells have a bright (white) inner top edge ~3px down
    top = cell[3:6, 6:26].reshape(-1, 3)
    bright = (top.sum(axis=1) > 640).mean()
    ctr = cell[9:23, 9:23].reshape(-1, 3)
    R, G, B = ctr[:, 0], ctr[:, 1], ctr[:, 2]
    red = ((R > 150) & (G < 100) & (B < 100)).sum()
    blue = ((B > 120) & (R < 110) & (G < 110)).sum()
    dblue = ((B > 55) & (B < 130) & (R < 70) & (G < 70)).sum()
    green = ((G > 95) & (R < 110) & (B < 110)).sum()
    black = ((R < 60) & (G < 60) & (B < 60)).sum()
    white = ((R > 200) & (G > 200) & (B > 200)).sum()
    mean = ctr.mean()
    if bright > 0.5:  # raised bevel -> covered / flag / question
        if red > 12:
            return 'F'
        if black > 10:
            return '?'
        return '#'
    # revealed
    if red > 8 and black > 8:
        return '*'          # exploded / shown mine
    if black > 40:
        return '*'          # mine shown at game over
    if red > 10:
        return '3'
    if blue > 10:
        return '1'
    if dblue > 10:
        return '4'
    if green > 10:
        return '2'
    if black > 10:
        return '7'
    if abs(mean - 192) < 25:
        return '.'
    return ' '

def read_board(path):
    a = np.asarray(Image.open(path).convert('RGB'))
    grid = []
    for r in range(8):
        row = ''.join(classify(a, r, c) for c in range(8))
        grid.append(row)
    return grid

if __name__ == '__main__':
    for row in read_board(sys.argv[1]):
        print(row)
