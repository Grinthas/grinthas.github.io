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
        self.extra_textures = {}  # текстуры не из textures/ (например, ядро энергокуба Mekanism)
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
        if ref in self.extra_textures:
            return self.extra_textures[ref]
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


def project(x, y, z):
    """Точка модели (0..16) на экране; смотрим с северо-запада сверху: север слева, запад справа."""
    s, h = SIZE, SIZE / 4
    return (s / 2 - x * s / 32 + z * s / 32, 2 * h - (x + z) * h / 16 + (16 - y) * s / 32)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def face_texture(assets, textures, f, default_uv):
    ref = resolve(textures, f["texture"])
    tex = assets.texture(ref) if ref else None
    if tex is None:
        return None
    u1, v1, u2, v2 = f.get("uv", default_uv)
    k = tex.width / 16
    box = [min(u1, u2) * k, min(v1, v2) * k, max(u1, u2) * k, max(v1, v2) * k]
    box = [int(box[0]), int(box[1]), max(int(box[0]) + 1, round(box[2])), max(int(box[1]) + 1, round(box[3]))]
    crop = tex.crop(tuple(box))
    if u1 > u2:
        crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
    if v1 > v2:
        crop = crop.transpose(Image.FLIP_TOP_BOTTOM)
    if f.get("rotation"):
        crop = crop.rotate(-f["rotation"], expand=True)
    return crop


def render_elements(assets, textures, elements, tint=None):
    """Рисует модель из нескольких деталей: видимые грани (верх, север, запад) от дальних к ближним."""
    faces = []
    for el in elements:
        (x1, y1, z1), (x2, y2, z2) = el["from"], el["to"]
        fs = el.get("faces") or {}
        if "up" in fs and x2 > x1 and z2 > z1:
            o = project(x1, y2, z1)
            faces.append(((x1 + x2) / 2 + (z1 + z2) / 2 - y2 * 2, fs["up"], [x1, z1, x2, z2],
                          o, sub(project(x2, y2, z1), o), sub(project(x1, y2, z2), o), 1.0))
        if "north" in fs and x2 > x1 and y2 > y1:
            o = project(x2, y2, z1)
            faces.append(((x1 + x2) / 2 + z1 * 2 - (y1 + y2) / 2, fs["north"], [16 - x2, 16 - y2, 16 - x1, 16 - y1],
                          o, sub(project(x1, y2, z1), o), sub(project(x2, y1, z1), o), 0.8))
        if "west" in fs and z2 > z1 and y2 > y1:
            o = project(x1, y2, z1)
            faces.append((x1 * 2 + (z1 + z2) / 2 - (y1 + y2) / 2, fs["west"], [z1, 16 - y2, z2, 16 - y1],
                          o, sub(project(x1, y2, z2), o), sub(project(x1, y1, z1), o), 0.62))
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for _, f, uv, o, u, v, light in sorted(faces, key=lambda t: -t[0]):
        tex = face_texture(assets, textures, f, uv)
        if tex is None or abs(u[0] * v[1] - u[1] * v[0]) < 1e-6:
            continue
        if tint and f["texture"] == "#core":
            tex = tinted(tex, tint)
        out.alpha_composite(shade(parallelogram(tex, o, u, v), light))
    return out


def tinted(tex, color):
    """Светящаяся текстура в цвете: узор задаёт яркость от 55% до 100% цвета, без прозрачности."""
    gray = tex.convert("L")
    rgb = [gray.point(lambda p, c=c: int(c * (0.55 + 0.45 * p / 255))) for c in color]
    return Image.merge("RGBA", (*rgb, Image.new("L", tex.size, 255)))


def is_full_cube(elements):
    return len(elements) == 1 and elements[0]["from"] == [0, 0, 0] and elements[0]["to"] == [16, 16, 16]


def mekanism_energy_cube(assets, chain, textures):
    """Энергокуб Mekanism: рамка из модели плюс ядро, которое в игре рисует код, в цвете уголков уровня."""
    frame = next((m["frame"] for _, m in chain if m.get("frame")), None)
    if not frame:
        return None
    corner = assets.texture(resolve(textures, "corner") or "")
    color = (255, 255, 255)
    if corner:
        px = [p for p in corner.convert("RGBA").getdata() if p[3] > 0 and max(p[:3]) - min(p[:3]) > 30]
        if px:
            color = tuple(sum(p[i] for p in px) // len(px) for i in range(3))
    raw = assets.read("assets/mekanism/render/energy_core.png")
    core_faces = {}
    if raw:
        textures = dict(textures, core="mekanism:__core__")
        core = Image.open(io.BytesIO(raw)).convert("RGBA")
        # текстура ядра — 4 одинаковые плитки 2×2, берём одну
        assets.extra_textures["mekanism:__core__"] = core.crop((0, 0, max(1, core.width // 2), max(1, core.height // 2)))
        core_faces = {f: {"texture": "#core", "uv": [0, 0, 16, 16]} for f in ("up", "north", "west")}
    elements = ([{"from": [4.5, 4.5, 4.5], "to": [11.5, 11.5, 11.5], "faces": core_faces}] if core_faces else []) + frame
    return render_elements(assets, textures, elements, tint=color)


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


def blockstate_model(assets, ns, name):
    """Модель первого варианта из blockstates/<name>.json."""
    bs = assets.json(f"assets/{ns}/blockstates/{name}.json")
    if not bs:
        return None
    variants = bs.get("variants") or {}
    for v in variants.values():
        v = v[0] if isinstance(v, list) else v
        return v.get("model")
    for part in bs.get("multipart", []):
        a = part.get("apply")
        a = a[0] if isinstance(a, list) else a
        return a.get("model")
    return None


def chest(assets):
    t = assets.texture("entity/chest/normal")
    top = t.crop((28, 0, 42, 14)).transpose(Image.FLIP_TOP_BOTTOM)  # (14..28) — нижняя сторона крышки, изнутри
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
    if not chain or chain[-1][0] == "builtin/entity":
        # предмет рисуется кодом (например, баки Mekanism): берём модель блока из blockstate
        chain = model_chain(assets, blockstate_model(assets, ns, name) or f"{ns}:block/{name}")
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

    if any(m.get("frame") for _, m in chain):
        return mekanism_energy_cube(assets, chain, textures)
    if elements and not is_full_cube(elements):
        return render_elements(assets, textures, elements)

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
        items.update(g["recipes"])
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
