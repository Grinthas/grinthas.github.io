"""Переносит гайды из внутриигрового гайда (grintguide) в guides/<project id>.json.

Запускается локально, когда гайд или рецепты мода изменились:
    py tools/import_guides.py
Берёт главы гайда (en_us/ru_ru), названия предметов из lang-файлов модов
и рецепты крафта из исходников/jar. Результат коммитится, сайт собирается из него.
"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDE = r"C:\mods\grintguide\src\main\resources\assets\grintguide\guide"

# ключ мода в гайде → Project ID на CurseForge и откуда брать lang/рецепты
MODS = {
    "industrialfurnace": {"project": 1761018, "source": r"C:\mods\mod\src\main\resources"},
    "ae2cpubox": {"project": 1761067, "source": r"C:\Users\bogba\Downloads\AE2 Crafting CPU Box\ae2cpubox-1.20.1-1.1.0.jar"},
    "automaticspawner": {"project": 1762978, "source": r"C:\Users\bogba\Downloads\AutomaticSpawner\automaticspawner-1.20.1-1.1.0.jar"},
}

# предметы других модов и ванили, которые встречаются в гайдах и рецептах
EXTRA_NAMES = {
    "minecraft:iron_ingot": ("Iron Ingot", "Железный слиток"),
    "minecraft:copper_ingot": ("Copper Ingot", "Медный слиток"),
    "minecraft:gold_ingot": ("Gold Ingot", "Золотой слиток"),
    "minecraft:brick": ("Brick", "Кирпич"),
    "minecraft:bricks": ("Bricks", "Кирпичи"),
    "minecraft:redstone": ("Redstone Dust", "Редстоун"),
    "minecraft:redstone_block": ("Block of Redstone", "Редстоуновый блок"),
    "minecraft:glass": ("Glass", "Стекло"),
    "minecraft:furnace": ("Furnace", "Печь"),
    "minecraft:blast_furnace": ("Blast Furnace", "Плавильная печь"),
    "minecraft:hopper": ("Hopper", "Воронка"),
    "minecraft:chest": ("Chest", "Сундук"),
    "minecraft:bucket": ("Bucket", "Ведро"),
    "minecraft:diamond": ("Diamond", "Алмаз"),
    "minecraft:diamond_block": ("Block of Diamond", "Алмазный блок"),
    "minecraft:emerald": ("Emerald", "Изумруд"),
    "minecraft:netherite_ingot": ("Netherite Ingot", "Незеритовый слиток"),
    "minecraft:nether_star": ("Nether Star", "Звезда Незера"),
    "minecraft:obsidian": ("Obsidian", "Обсидиан"),
    "minecraft:piston": ("Piston", "Поршень"),
    "minecraft:grindstone": ("Grindstone", "Точило"),
    "minecraft:cauldron": ("Cauldron", "Котёл"),
    "minecraft:blaze_rod": ("Blaze Rod", "Огненный стержень"),
    "minecraft:blaze_powder": ("Blaze Powder", "Огненный порошок"),
    "minecraft:iron_block": ("Block of Iron", "Железный блок"),
    "minecraft:gold_block": ("Block of Gold", "Золотой блок"),
    "minecraft:comparator": ("Redstone Comparator", "Компаратор"),
    "minecraft:ender_pearl": ("Ender Pearl", "Жемчуг Края"),
    "minecraft:ender_eye": ("Eye of Ender", "Око Края"),
    "minecraft:crafting_table": ("Crafting Table", "Верстак"),
    "minecraft:quartz": ("Nether Quartz", "Кварц Незера"),
    "minecraft:glowstone_dust": ("Glowstone Dust", "Светокаменная пыль"),
    "minecraft:lava_bucket": ("Lava Bucket", "Ведро лавы"),
    "minecraft:water_bucket": ("Water Bucket", "Ведро воды"),
    "minecraft:brewing_stand": ("Brewing Stand", "Варочная стойка"),
    "minecraft:anvil": ("Anvil", "Наковальня"),
    "minecraft:smithing_table": ("Smithing Table", "Стол кузнеца"),
    "minecraft:beacon": ("Beacon", "Маяк"),
    "minecraft:tinted_glass": ("Tinted Glass", "Тонированное стекло"),
    "minecraft:iron_bars": ("Iron Bars", "Железная решётка"),
    "minecraft:amethyst_shard": ("Amethyst Shard", "Осколок аметиста"),
    "minecraft:gunpowder": ("Gunpowder", "Порох"),
    "minecraft:sugar": ("Sugar", "Сахар"),
    "minecraft:dropper": ("Dropper", "Выбрасыватель"),
    "minecraft:crying_obsidian": ("Crying Obsidian", "Плачущий обсидиан"),
    "minecraft:experience_bottle": ("Bottle o' Enchanting", "Пузырёк опыта"),
    "minecraft:ghast_tear": ("Ghast Tear", "Слеза гаста"),
    "minecraft:lapis_lazuli": ("Lapis Lazuli", "Лазурит"),
    "minecraft:sticky_piston": ("Sticky Piston", "Липкий поршень"),
    "mekanism:alloy_atomic": ("Atomic Alloy", "Атомный сплав"),
    "mekanism:ingot_refined_obsidian": ("Refined Obsidian Ingot", "Слиток очищенного обсидиана"),
    "mekanism:ingot_steel": ("Steel Ingot", "Стальной слиток"),
    "mekanism:ultimate_control_circuit": ("Ultimate Control Circuit", "Совершенная схема управления"),
    "avaritia:crystal_matrix_ingot": ("Crystal Matrix Ingot", "Слиток кристаллической матрицы"),
    "avaritia:extreme_crafting_table": ("Extreme Crafting Table", "Экстремальный верстак"),
    "avaritia:neutron_ingot": ("Neutronium Ingot", "Нейтрониевый слиток"),
    "draconicevolution:awakened_core": ("Awakened Core", "Пробуждённое ядро"),
    "draconicevolution:draconium_core": ("Draconium Core", "Дракониевое ядро"),
    "draconicevolution:draconium_ingot": ("Draconium Ingot", "Дракониевый слиток"),
    "draconicevolution:wyvern_core": ("Wyvern Core", "Ядро виверны"),
    "ae2:crafting_unit": ("Crafting Unit", "Блок крафта"),
    "ae2:crafting_accelerator": ("Crafting Co-Processing Unit", "Сопроцессор крафта"),
    "ae2:1k_crafting_storage": ("1k Crafting Storage", "Хранилище крафта 1k"),
    "ae2:4k_crafting_storage": ("4k Crafting Storage", "Хранилище крафта 4k"),
    "ae2:16k_crafting_storage": ("16k Crafting Storage", "Хранилище крафта 16k"),
    "ae2:64k_crafting_storage": ("64k Crafting Storage", "Хранилище крафта 64k"),
    "ae2:256k_crafting_storage": ("256k Crafting Storage", "Хранилище крафта 256k"),
    "ae2:logic_processor": ("Logic Processor", "Логический процессор"),
    "ae2:calculation_processor": ("Calculation Processor", "Вычислительный процессор"),
    "ae2:engineering_processor": ("Engineering Processor", "Инженерный процессор"),
    "ae2:fluix_crystal": ("Fluix Crystal", "Кристалл флюикса"),
    "ae2:certus_quartz_crystal": ("Certus Quartz Crystal", "Кристалл истинного кварца"),
    "ae2:quartz_glass": ("Quartz Glass", "Кварцевое стекло"),
    "ae2:fluix_glass_cable": ("Fluix Glass Cable", "Стеклянный кабель из флюикса"),
    "ae2:interface": ("ME Interface", "ME-интерфейс"),
    "ae2:pattern_provider": ("Pattern Provider", "Поставщик шаблонов"),
    "ae2:sky_stone_block": ("Sky Stone", "Небесный камень"),
}

TAG_NAMES = {
    "forge:ingots/iron": ("Iron Ingot", "Железный слиток"),
    "forge:ingots/copper": ("Copper Ingot", "Медный слиток"),
    "forge:ingots/gold": ("Gold Ingot", "Золотой слиток"),
    "forge:glass": ("Glass", "Стекло"),
    "forge:dusts/redstone": ("Redstone Dust", "Редстоун"),
    "forge:gems/diamond": ("Diamond", "Алмаз"),
    "forge:storage_blocks/iron": ("Block of Iron", "Железный блок"),
    "forge:obsidian": ("Obsidian", "Обсидиан"),
    "forge:chests": ("Chest", "Сундук"),
}


def read_source(src):
    """{путь внутри ресурсов: bytes} для lang и рецептов из папки или jar."""
    out = {}
    if src.endswith(".jar"):
        with zipfile.ZipFile(src) as z:
            for n in z.namelist():
                if ("/lang/" in n or "/recipes/" in n) and n.endswith(".json"):
                    out[n] = z.read(n)
    else:
        for root, _, files in os.walk(src):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, src).replace("\\", "/")
                if ("/lang/" in rel or "/recipes/" in rel) and f.endswith(".json"):
                    with open(p, "rb") as fh:
                        out[rel] = fh.read()
    return out


def lang_names(files, modid):
    names = {}
    for lang, idx in (("en_us", 0), ("ru_ru", 1)):
        data = json.loads(files.get(f"assets/{modid}/lang/{lang}.json", b"{}").decode("utf-8-sig"))
        for k, v in data.items():
            kind, _, rest = k.partition(".")
            if kind in ("block", "item") and rest.startswith(modid + ".") and rest.count(".") == 1:
                item = rest.replace(".", ":", 1)
                names.setdefault(item, ["", ""])[idx] = v
    return names


def ingredient(ing):
    if isinstance(ing, list):
        ing = ing[0]
    return ing.get("item") or ("#" + ing["tag"])


def recipes(files, modid):
    out = {}
    for path, raw in files.items():
        if not path.startswith(f"data/{modid}/recipes/") or path.count("/") != 3:
            continue
        r = json.loads(raw.decode("utf-8-sig"))
        if r.get("type") != "minecraft:crafting_shaped":
            continue
        res = r["result"]
        out[res["item"]] = {
            "pattern": r["pattern"],
            "key": {k: ingredient(v) for k, v in r["key"].items()},
            "count": res.get("count", 1),
        }
    return out


def collect_ids(chapters, recs):
    ids = set()
    for ch in chapters:
        ids.add(ch.get("icon", ""))
        for b in ch["blocks"]:
            ids.update(b.get("items", []))
            if "recipe" in b:
                ids.add(b["recipe"])
    for r in recs.values():
        ids.update(r["key"].values())
    return {i for i in ids if i}


def main():
    guide = {}
    for lang in ("en_us", "ru_ru"):
        with open(os.path.join(GUIDE, f"{lang}.json"), encoding="utf-8-sig") as f:
            guide[lang] = {m["mod"]: m for m in json.load(f)["mods"]}

    os.makedirs(os.path.join(HERE, "guides"), exist_ok=True)
    for modid, cfg in MODS.items():
        files = read_source(cfg["source"])
        names = lang_names(files, modid)
        recs = recipes(files, modid)
        missing = []
        for i in collect_ids(guide["en_us"][modid]["chapters"], recs):
            if i in names:
                continue
            if i.startswith("#"):
                pair = TAG_NAMES.get(i[1:])
            else:
                pair = EXTRA_NAMES.get(i)
            if pair:
                names[i] = list(pair)
            else:
                missing.append(i)
        out = {
            "en": guide["en_us"][modid]["chapters"],
            "ru": guide["ru_ru"][modid]["chapters"],
            "names": dict(sorted(names.items())),
            "recipes": dict(sorted(recs.items())),
        }
        path = os.path.join(HERE, "guides", f"{cfg['project']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"{modid} → {path}: {len(out['en'])} глав, {len(recs)} рецептов")
        if missing:
            print("  без названия:", ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
