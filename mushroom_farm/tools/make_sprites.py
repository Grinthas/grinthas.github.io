#!/usr/bin/env python3
"""Рисует пиксельные заглушки в папку assets/.
Запуск:  python3 tools/make_sprites.py
Любую картинку можно заменить своей (тот же размер и имя файла) - код менять не надо.
Розовый цвет (255, 0, 255) на шляпке гриба игра сама перекрашивает в цвет гриба."""
import os, random
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(OUT, exist_ok=True)

PAL = {
    ".": None,
    "k": (43, 29, 20), "h": (224, 184, 74), "H": (176, 138, 42),
    "s": (240, 192, 144), "e": (34, 34, 34), "b": (58, 110, 165), "B": (44, 82, 130),
    "p": (107, 74, 43), "o": (58, 38, 22),
    "m": (107, 69, 40), "l": (138, 90, 53), "d": (74, 48, 32),
    "g": (88, 170, 74), "M": (255, 0, 255), "W": (255, 255, 255),
    "S": (232, 220, 192), "t": (190, 176, 146),
    "r": (110, 110, 118), "R": (150, 150, 160), "q": (72, 72, 80),
    "y": (255, 214, 64), "Y": (214, 160, 32),
}

def sprite(name, rows, w=16, h=16):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rows = list(rows)
    assert len(rows) <= h, (name, "слишком много строк")
    for y, row in enumerate(rows):
        assert len(row) <= w, (name, y, len(row))
        for x, ch in enumerate(row.ljust(w, ".")):
            c = PAL[ch]
            if c:
                img.putpixel((x, y), c + (255,))
    img.save(os.path.join(OUT, name + ".png"))

E = "................"

sprite("farmer", [
    E,
    ".....kkkkkk.....",
    "....khhhhhhk....",
    "...khhHhhHhhk...",
    "..kkkkkkkkkkkk..",
    "...kssssssssk...",
    "...kssessessk...",
    "...kssssssssk...",
    "....kksssskk....",
    "...kbbbbbbbbk...",
    "..kbbBbbbbBbbk..",
    "..ksbbbbbbbbsk..",
    "...kbbbbbbbbk...",
    "...kppppppppk...",
    "...kpppkkpppk...",
    "..kooookkooook..",
])

sprite("bed", [
    E, E, E, E, E, E,
    "..kkkkkkkkkkkk..",
    ".kmmmmmmmmmmmmk.",
    "kmmlmmmmmlmmmmmk",
    "kmmmmmdmmmmmdmmk",
    "kmlmmmmmmmlmmmmk",
    "kmmmmmdmmmmmmmmk",
    "kmmdmmmmmmdmmmmk",
    ".kmmmmmmmmmmmmk.",
    "..kddddddddddk..",
    "...kkkkkkkkkk...",
])

sprite("shroom_1", [   # росток
    E, E, E, E, E,
    "......g...g.....",
    ".......g.g......",
    "........g.......",
    "........g.......",
])

sprite("shroom_2", [   # растёт
    E, E, E,
    "................",
    "......kkkk......",
    ".....kMMMMk.....",
    ".....kMWMMk.....",
    ".....kkSSkk.....",
    "......kSSk......",
    "......kSSk......",
])

sprite("shroom_3", [   # готов
    E,
    "......kkkk......",
    "....kkMMMMkk....",
    "...kMMMWMMMMk...",
    "..kMMWWMMMMWMk..",
    "..kMMMMMMMMMMk..",
    "..kkkkkkkkkkkk..",
    "......kSSk......",
    "......kSSk......",
    "......kStk......",
    ".....kkSSkk.....",
])

sprite("rock", [       # завал: грядка ещё не открыта
    E, E, E,
    "................",
    ".....kkkkk......",
    "....kRRRRrkk....",
    "...kRRrrrrrrk...",
    "..kRrrrrqrrrrk..",
    "..krrrqrrrrRrk..",
    ".kRrrrrrrrrrrrk.",
    ".krrqrrrrqrrrrk.",
    ".kqrrrrrrrrrqqk.",
    "..kqqrrrrqqqk...",
    "...kkkkkkkkkk...",
])

sprite("marker", [     # стрелка над ближайшей грядкой
    "kkkkkkkk",
    "kyyyyyyk",
    ".kyyyyk.",
    "..kyyk..",
    "...kk...",
], w=8, h=8)

sprite("coin", [
    "..kkkk..",
    ".kyyyyk.",
    "kyyYYyyk",
    "kyYyyYyk",
    "kyYyyYyk",
    "kyyYYyyk",
    ".kyyyyk.",
    "..kkkk..",
], w=8, h=8)

def tile(name, base, spots, seed, mortar=None):
    random.seed(seed)
    img = Image.new("RGBA", (16, 16), base + (255,))
    for _ in range(14):
        x, y = random.randrange(16), random.randrange(16)
        img.putpixel((x, y), random.choice(spots) + (255,))
    if mortar:   # кирпичная кладка
        for y in (0, 8):
            for x in range(16):
                img.putpixel((x, y), mortar + (255,))
        for y, xs in ((1, (3, 11)), (9, (7, 15))):
            for yy in range(y, y + 7):
                for x in xs:
                    img.putpixel((x, yy), mortar + (255,))
    img.save(os.path.join(OUT, name + ".png"))

tile("floor_a", (59, 47, 39), [(50, 39, 32), (68, 55, 46), (76, 62, 52)], 1)
tile("floor_b", (55, 44, 36), [(46, 36, 30), (64, 52, 43), (72, 58, 49)], 2)
tile("wall", (92, 76, 66), [(80, 66, 57), (104, 88, 76)], 3, mortar=(46, 36, 31))

print("Готово:", sorted(os.listdir(OUT)))
