"""Рисует иконки предметов из гайдов в guides/icons/<ns>__<name>.png.

Запускается локально после tools/import_guides.py:
    py tools/import_icons.py
Текстуры берутся из jar-файлов Minecraft и модов (пути ниже). Плоские предметы
увеличиваются как есть, блоки рисуются изометрическим кубом, как в инвентаре.
"""
import glob
import io
import json
import os
import zipfile

from PIL import Image, ImageEnhance

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "guides", "icons")
SIZE = 64
MC = os.path.expanduser(r"~\.minecraftx")
SOURCES = [
    r"C:\mods\mod\src\main\resources",
    os.path.join(MC, r"instances\my mods\mods"),
    os.path.join(MC, r"versions\1.20.1\1.20.1.jar"),
]


class Assets:
    """Ресурсы из папок и jar-файлов; первый найденный файл побеждает."""

    def __init__(self, sources):
        self.index = {}
        for src in sources:
            if os.path.isdir(src) and not glob.glob(os.path.join(src, "*.jar")):
                for root, _, files in os.walk(src):
                    for f in files:
                        p = os.path.join(root, f)
                        rel = os.path.relpath(p, src).replace("\\", "/")
                        self.index.setdefault(rel, ("dir", p))
            else:
                jars = glob.glob(os.path.join(src, "*.jar")) if os.path.isdir(src) else [src]
                for jar in jars:
                    z = zipfile.ZipFile(jar)
                    for n in z.namelist():
                        if n.startswith("assets/"):
                            self.index.setdefault(n, ("zip", z))

    def read(self, path):
        hit = self.index.get(path)
        if not hit:
            return None
        kind, src = hit
        if kind == "dir":
            with open(src, "rb") as f:
                return f.read()
        return src.read(path)

    def json(self, path):
        raw = self.read(path)
        return json.loads(raw.decode("utf-8-sig")) if raw else None

    def texture(self, ref):
        ns, _, name = ref.partition(":") if ":" in ref else ("minecraft", "", ref)
        raw = self.read(f"assets/{ns}/textures/{name}.png")
        if not raw:
            return None
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        if img.height > img.width:  # анимация: берём первый кадр
            img = img.crop((0, 0, img.width, img.width))
        return img


def split(ref):
    return ref.split(":", 1) if ":" in ref else ("minecraft", ref)


def model_chain(assets, ref):
    """Цепочка моделей от предмета к корню: [(ref, json), ...]."""
    chain = []
    while ref and len(chain) < 12:
        if ref.startswith("builtin/"):
            chain.append((ref, {}))
            break
        ns, name = split(ref)
        m = assets.json(f"assets/{ns}/models/{name}.json")
        if m is None:
            break
        chain.append((f"{ns}:{name}", m))
        ref = m.get("parent")
    return chain


def resolve(textures, key, depth=0):
    v = textures.get(key.lstrip("#"))
    if v and v.startswith("#") and depth < 8:
        return resolve(textures, v, depth + 1)
    return v


def parallelogram(tex, origin, u, v):
    """Натягивает квадратную текстуру на параллелограмм origin + x*u + y*v."""
    src = tex.resize((SIZE, SIZE), Image.NEAREST)
    a, b, c, d = u[0] / SIZE, v[0] / SIZE, u[1] / SIZE, v[1] / SIZE
    det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    ox, oy = origin
    data = (ia, ib, -(ia * ox + ib * oy), ic, id_, -(ic * ox + id_ * oy))
    return src.transform((SIZE, SIZE), Image.AFFINE, data, resample=Image.NEAREST, fillcolor=(0, 0, 0, 0))


def shade(img, k):
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(k)
    rgb.putalpha(img.getchannel("A"))
    return rgb


def cube(top, left, right):
    s = SIZE
    h = s * 0.25
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # левая и правая грани, затем крышка
    out.alpha_composite(shade(parallelogram(left, (0, h), (s / 2, h), (0, s / 2)), 0.78))
    out.alpha_composite(shade(parallelogram(right, (s / 2, 2 * h), (s / 2, -h), (0, s / 2)), 0.6))
    out.alpha_composite(parallelogram(top, (0, h), (s / 2, -h), (s / 2, h)))
    return out


def face(assets, textures, element, name):
    f = (element.get("faces") or {}).get(name)
    if not f:
        return None
    ref = resolve(textures, f["texture"])
    tex = assets.texture(ref) if ref else None
    if tex and "uv" in f:
        u1, v1, u2, v2 = f["uv"]
        k = tex.width / 16
        box = (min(u1, u2) * k, min(v1, v2) * k, max(u1, u2) * k, max(v1, v2) * k)
        if box[2] > box[0] and box[3] > box[1]:
            tex = tex.crop(tuple(int(x) for x in box))
    return tex


def chest(assets):
    t = assets.texture("entity/chest/normal")
    top = t.crop((14, 0, 28, 14))
    front = Image.new("RGBA", (14, 15))
    front.paste(t.crop((14, 14, 28, 19)), (0, 0))
    front.paste(t.crop((14, 33, 28, 43)), (0, 5))
    side = Image.new("RGBA", (14, 15))
    side.paste(t.crop((0, 14, 14, 19)), (0, 0))
    side.paste(t.crop((0, 33, 14, 43)), (0, 5))
    return cube(top, front, side)


def icon(assets, item):
    ns, name = split(item)
    if item == "minecraft:chest":
        return chest(assets)
    chain = model_chain(assets, f"{ns}:item/{name}")
    if not chain:
        chain = model_chain(assets, f"{ns}:block/{name}")
    textures, elements = {}, None
    for _, m in reversed(chain):
        textures.update(m.get("textures") or {})
    for _, m in chain:
        if m.get("elements"):
            elements = m["elements"]
            break
    refs = [r for r, _ in chain]

    flat = any(r.endswith(("item/generated", "item/handheld")) or r == "builtin/generated" for r in refs)
    if flat or (not elements and "layer0" in textures):
        out = None
        for i in range(5):
            ref = textures.get(f"layer{i}")
            tex = assets.texture(ref) if ref else None
            if tex is None:
                continue
            tex = tex.resize((SIZE, SIZE), Image.NEAREST)
            out = tex if out is None else Image.alpha_composite(out, tex)
        return out

    if elements:
        def volume(e):
            return abs((e["to"][0] - e["from"][0]) * (e["to"][1] - e["from"][1]) * (e["to"][2] - e["from"][2]))
        el = max(elements, key=volume)
        top = face(assets, textures, el, "up")
        left = face(assets, textures, el, "north")
        right = face(assets, textures, el, "east")
    else:
        top = left = right = None
    fallback = None
    for key in ("all", "side", "particle", "texture", "front", "top", "end"):
        ref = resolve(textures, key)
        if ref and assets.texture(ref):
            fallback = assets.texture(ref)
            break
    top, left, right = top or fallback, left or fallback, right or fallback
    if not (top and left and right):
        return None
    return cube(top, left, right)


def main():
    assets = Assets(SOURCES)
    items = set()
    for path in glob.glob(os.path.join(HERE, "guides", "*.json")):
        with open(path, encoding="utf-8") as f:
            g = json.load(f)
        items.update(i for i in g["names"] if not i.startswith("#"))
    os.makedirs(OUT, exist_ok=True)
    missing = []
    for item in sorted(items):
        img = icon(assets, item)
        if img is None:
            missing.append(item)
            continue
        img.save(os.path.join(OUT, item.replace(":", "__") + ".png"), optimize=True)
    print(f"Иконок: {len(items) - len(missing)} из {len(items)} → {OUT}")
    if missing:
        print("  без иконки:", ", ".join(missing))


if __name__ == "__main__":
    main()
