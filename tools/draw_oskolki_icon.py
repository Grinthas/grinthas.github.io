"""Draws modpacks/oskolki.png: the pack icon, a floating island split by a burning rift (pixel art, 32×32 ×4)."""
import os
import random

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "modpacks", "oskolki.png")
S = 32
im = Image.new("RGBA", (S, S), (16, 10, 28, 255))
px = im.load()
rnd = random.Random(5)

# night sky with a few stars and a lighter band in the middle
for y in range(S):
    for x in range(S):
        if 9 <= y <= 22:
            px[x, y] = (22, 14, 38, 255)
for _ in range(22):
    px[rnd.randrange(S), rnd.randrange(S)] = (220, 200, 255, 255)

CX = 16
crack = [CX + d for d in (0, 1, 1, 0, -1, -1, 0, 1, 2, 1, 0, -1, 0, 1, 1, 0, -1, -1, 0, 1, 1, 0, 0, -1, -1, 0, 1, 1, 0, 0, -1, 0)]

# the island torn in two: grass, dirt, stone tapering down, halves pushed apart
for side in (-1, 1):
    for i in range(12):
        x = CX + side * (2 + i)
        depth = max(1, int((1 - (i / 12) ** 2) * 9))
        for y in range(depth):
            c = (122, 79, 46) if y == 0 else (92, 95, 104) if (x + y) % 3 else (70, 72, 82)
            px[x, 18 + y] = c + (255,)
        px[x, 17] = (108, 191, 63, 255) if i % 3 else (90, 168, 52, 255)
    px[CX + side * 6, 21] = (79, 216, 224, 255)
    px[CX + side * 9, 19] = (79, 216, 224, 255)
    # the edge facing the rift glows
    for y in range(17, 25):
        if px[CX + side * 2, y][3] and px[CX + side * 2, y][:3] != (22, 14, 38):
            r, g, b, a = px[CX + side * 2, y]
            px[CX + side * 2, y] = (min(255, r + 90), min(255, g + 50), b, 255)

# the rift: a glow, the hot core and embers
for y in range(S):
    x = crack[y]
    for dx, c in ((-2, (120, 50, 20)), (2, (120, 50, 20)), (-1, (255, 138, 31)), (1, (255, 138, 31))):
        if 0 <= x + dx < S:
            px[x + dx, y] = c + (255,)
    px[x, y] = (255, 244, 194, 255) if y % 3 == 0 else (255, 211, 107, 255)
for x, y in ((12, 6), (21, 9), (11, 13), (22, 4)):
    px[x, y] = (180, 108, 255, 255)

# a dark frame so the icon reads on any background
for i in range(S):
    for p in ((i, 0), (i, S - 1), (0, i), (S - 1, i)):
        px[p] = (8, 5, 14, 255)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
im.resize((S * 4, S * 4), Image.NEAREST).save(OUT)
print(OUT)
