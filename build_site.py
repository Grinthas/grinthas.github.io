"""Собирает статический сайт с модами из mods.txt в папку _site.

Нужен CF_API_KEY. Сайт двуязычный (EN/RU): строки интерфейса переключаются
кнопкой, описания модов берутся с CurseForge.

Русские описания лежат в translations/<id>.json вместе с sha1 английского
оригинала. Если оригинал на CurseForge изменился (или перевода нет), то при
заданном AUTO_TRANSLATE=1 перевод делается заново офлайн через Argos Translate
и сохраняется, иначе в русской версии показывается английский.
Флаг --stamp проставляет sha1 в переводах, где он пустой (после ручного перевода).
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import subprocess
from datetime import datetime, timezone

from notify import HERE, STATUS_APPROVED, cf, listed_ids

OUT = os.path.join(HERE, "_site")
TRANSLATIONS = os.path.join(HERE, "translations")
GUIDES = os.path.join(HERE, "guides")
ICONS = os.path.join(GUIDES, "icons")
PROFILE = "https://www.curseforge.com/members/grint/projects"
LOADERS = {"Forge", "NeoForge", "Fabric", "Quilt"}
RELEASE = {1: ("Release", "Релиз", "release"), 2: ("Beta", "Бета", "beta"), 3: ("Alpha", "Альфа", "alpha")}


def t(en, ru):
    """Строка интерфейса на двух языках; видимую выбирает CSS по lang у <html>."""
    return f'<span lang="en">{html.escape(en)}</span><span lang="ru">{html.escape(ru)}</span>'


def bilingual(tag, en, ru, cls=""):
    """Блок с английским и русским вариантом; без перевода — только английский."""
    c = f' class="{cls}"' if cls else ""
    if ru is None:
        return f"<{tag}{c}>{en}</{tag}>"
    return f'<{tag}{c} lang="en">{en}</{tag}><{tag}{c} lang="ru">{ru}</{tag}>'


def source_sha1(summary, description):
    return hashlib.sha1(f"{summary}\n{description}".encode("utf-8")).hexdigest()


_translator = None


def translate(text, is_html):
    """Офлайн-перевод EN→RU через Argos Translate (ставится при первой надобности)."""
    global _translator
    if _translator is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "argostranslate", "translatehtml"])
        import argostranslate.package
        import argostranslate.translate
        argostranslate.package.update_package_index()
        pkg = next(p for p in argostranslate.package.get_available_packages()
                   if p.from_code == "en" and p.to_code == "ru")
        argostranslate.package.install_from_path(pkg.download())
        _translator = argostranslate.translate.get_translation_from_codes("en", "ru")
    if not is_html:
        return _translator.translate(text)
    from translatehtml import translate_html
    return str(translate_html(_translator, text))


def russian(mod, description, stamp=False):
    """(summary, description) на русском или None, если актуального перевода нет."""
    path = os.path.join(TRANSLATIONS, f"{mod['id']}.json")
    sha = source_sha1(mod.get("summary", ""), description)
    tr = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            tr = json.load(f)
        if stamp and not tr["source_sha1"]:
            tr["source_sha1"] = sha
            save_translation(path, tr)
        if tr["source_sha1"] == sha:
            return tr["summary"], tr["description"]
    if not os.environ.get("AUTO_TRANSLATE"):
        return None
    try:
        summary_ru = translate(mod.get("summary", ""), is_html=False)
        description_ru = translate(description, is_html=True)
    except Exception as e:
        # сбой установки или перевода: оставляем английский, повторим при следующей сборке
        print(f"Не удалось перевести {mod['name']}: {e}")
        return None
    tr = {"source_sha1": sha, "summary": summary_ru, "description": description_ru, "machine": True}
    save_translation(path, tr)
    print(f"Переведено через Argos Translate: {mod['name']}")
    return summary_ru, description_ru


def save_translation(path, tr):
    os.makedirs(TRANSLATIONS, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tr, f, ensure_ascii=False, indent=2)
        f.write("\n")


def files_of(mod_id):
    files, index = [], 0
    while True:
        page = cf(f"/mods/{mod_id}/files", {"index": index, "pageSize": 50})
        files += page
        index += len(page)
        if len(page) < 50:
            return sorted(files, key=lambda f: f["fileDate"], reverse=True)


def size(n):
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.0f} KB"


def date(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")[:19]).strftime("%Y-%m-%d")


def download_url(mod, f):
    return f["downloadUrl"] or f"{mod['links']['websiteUrl']}/files/{f['id']}"


def mod_info(mod, files):
    """Общие данные для карточки и страницы мода."""
    mc = sorted({v for f in files for v in f["gameVersions"] if re.match(r"\d", v)}, reverse=True)
    loaders = sorted({v for f in files for v in f["gameVersions"] if v in LOADERS})
    # основной файл, выбранный автором на CurseForge, иначе самый свежий
    latest = next((f for f in files if f["id"] == mod.get("mainFileId")), files[0] if files else None)
    return mc, loaders, latest


def latest_button(mod, latest):
    if not latest:
        return ""
    return (f'<a class="btn primary" href="{html.escape(download_url(mod, latest))}">'
            f'{t("Download latest", "Скачать последнюю")}<small>{html.escape(latest["displayName"])}</small></a>')


def render_card(mod, files, ru):
    """Карточка мода на главной: название ведёт на страницу мода."""
    e = html.escape
    summary_ru = ru[0] if ru else None
    mc, loaders, latest = mod_info(mod, files)
    page = f"mods/{e(mod['slug'])}/"
    logo = (mod.get("logo") or {}).get("url", "")
    tags = "".join(f"<li>{e(c['name'])}</li>" for c in mod["categories"])
    return f"""
  <article class="mod card">
    <a href="{page}"><img class="logo" src="{e(logo)}" alt="" width="96" height="96"></a>
    <div class="mod-title">
      <h2><a href="{page}">{e(mod['name'])}</a></h2>
      {bilingual('p', e(mod.get('summary', '')), e(summary_ru) if summary_ru else None, 'summary')}
      <ul class="tags">{tags}</ul>
      <p class="facts">Minecraft {e(', '.join(mc))} · {e(', '.join(loaders))} · {mod['downloadCount']:,} {t('downloads', 'загрузок')}</p>
      <div class="actions">
        <a class="btn" href="{page}">{t('Guide and details →', 'Гайд и подробности →')}</a>
        {latest_button(mod, latest)}
        <a class="btn ghost" href="{e(mod['links']['websiteUrl'])}" target="_blank" rel="noopener">CurseForge ↗</a>
      </div>
    </div>
  </article>"""


MC_COLORS = "0123456789abcdef"


def mc_text(s):
    """Текст гайда: экранирование и цветовые коды Minecraft (§a … §r)."""
    out, open_ = [], False
    for i, part in enumerate(re.split(r"§(.)", html.escape(s))):
        if i % 2 == 0:
            out.append(part)
            continue
        if open_:
            out.append("</span>")
            open_ = False
        if part.lower() in MC_COLORS:
            out.append(f'<span class="mc-{part.lower()}">')
            open_ = True
    if open_:
        out.append("</span>")
    return "".join(out)


def item_name(guide, item, lang):
    pair = guide["names"].get(item)
    if pair and pair[lang == "ru"]:
        return pair[lang == "ru"]
    return item.split(":")[-1].lstrip("#").replace("_", " ").title()


def item_icon(item, alt=""):
    """<img> иконки предмета из guides/icons или '' если её нет."""
    name = item.replace(":", "__") + ".png"
    path = os.path.join(ICONS, name)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        version = hashlib.sha1(f.read()).hexdigest()[:8]  # новая картинка — новый адрес, мимо кэша браузера
    return (f'<img class="icon" src="../../icons/{name}?v={version}" alt="{html.escape(alt)}" '
            f'width="32" height="32" loading="lazy">')


def item_chips(guide, items, lang):
    """Плашки предметов: id или [id, количество]."""
    chips = []
    for x in items:
        item, count = x if isinstance(x, list) else (x, 1)
        num = f"<b>{count}×</b>" if count > 1 else ""
        chips.append(f"<li>{item_icon(item)}{num}{html.escape(item_name(guide, item, lang))}</li>")
    return "".join(chips)


def render_recipe(guide, item, lang):
    e = html.escape
    r = guide["recipes"].get(item)
    if not r:
        return ""
    letters = sorted(r["key"])
    color = {k: i % 8 for i, k in enumerate(letters)}

    def slot(ch):
        name = item_name(guide, r["key"][ch], lang)
        img = item_icon(r["key"][ch], name)
        if img:
            return f'<span class="cell slot" title="{e(name)}">{img}</span>'
        return f'<span class="cell k{color[ch]}" title="{e(name)}">{e(ch)}</span>'

    cells = []
    for row in (r["pattern"] + ["", "", ""])[:3]:
        for ch in (row + "   ")[:3]:
            cells.append(slot(ch) if ch in r["key"] else '<span class="cell slot"></span>')
    legend = "".join(f'<li>{slot(k)}{e(item_name(guide, r["key"][k], lang))}</li>' for k in letters)
    count = f'<span class="count">{r["count"]}</span>' if r["count"] > 1 else ""
    name = item_name(guide, item, lang)
    return f"""
      <figure class="recipe">
        <div class="grid">{''.join(cells)}</div>
        <span class="arrow">→</span>
        <figcaption class="result"><span class="cell slot big" title="{e(name)}">{item_icon(item, name)}{count}</span>{e(name)}</figcaption>
        <ul class="legend">{legend}</ul>
      </figure>"""


def render_guide(guide, lang):
    e = html.escape
    toc, body = [], []
    for i, ch in enumerate(guide[lang]):
        anchor = f"{lang}-{i + 1}"
        toc.append(f'<li><a href="#{anchor}">{e(ch["title"])}</a></li>')
        blocks = []
        for b in ch["blocks"]:
            if "text" in b:
                blocks.append(f"<p>{mc_text(b['text'])}</p>")
            elif "heading" in b:
                blocks.append(f"<h4>{e(b['heading'])}</h4>")
            elif "items" in b:
                chips = item_chips(guide, b["items"], lang)
                blocks.append(f'<ul class="items">{chips}</ul>')
            elif "table" in b:
                rows = "".join(f"<tr><th>{mc_text(k)}</th><td>{mc_text(v)}</td></tr>" for k, v in b["table"])
                blocks.append(f'<div class="table-wrap"><table class="kv">{rows}</table></div>')
            elif "recipe" in b:
                blocks.append(render_recipe(guide, b["recipe"], lang))
            elif "forging" in b:
                f = b["forging"]
                name = item_name(guide, f["result"], lang)
                blocks.append(f"""
      <div class="forging">
        <div class="out"><span class="cell slot big" title="{e(name)}">{item_icon(f['result'], name)}</span>{e(name)}</div>
        <ul class="items">{item_chips(guide, f['inputs'], lang)}</ul>
        <p class="note">+ {mc_text(f['note'])}</p>
      </div>""")
        body.append(f'<section class="chapter" id="{anchor}"><h3>{e(ch["title"])}</h3>{"".join(blocks)}</section>')
    title = "Contents" if lang == "en" else "Содержание"
    return f"""
    <div class="guide" lang="{lang}">
      <nav class="toc"><p>{title}</p><ol>{''.join(toc)}</ol></nav>
      <div class="chapters">{''.join(body)}</div>
    </div>"""


def load_guide(mod_id):
    path = os.path.join(GUIDES, f"{mod_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def render_page(mod, files, description, ru, guide):
    """Отдельная страница мода: шапка, скриншоты, гайд, описание, все версии."""
    e = html.escape
    summary_ru, description_ru = ru or (None, None)
    mc, loaders, latest = mod_info(mod, files)
    logo = (mod.get("logo") or {}).get("url", "")
    tags = "".join(f"<li>{e(c['name'])}</li>" for c in mod["categories"])

    rows = []
    for f in files:
        en, ru_, cls = RELEASE.get(f["releaseType"], RELEASE[1])
        fmc = ", ".join(v for v in f["gameVersions"] if re.match(r"\d", v))
        floader = ", ".join(v for v in f["gameVersions"] if v in LOADERS)
        rows.append(f"""
        <tr>
          <td class="fname">{e(f['displayName'])}</td>
          <td>{e(fmc)}</td>
          <td>{e(floader)}</td>
          <td><span class="badge {cls}">{t(en, ru_)}</span></td>
          <td class="num">{date(f['fileDate'])}</td>
          <td class="num">{size(f['fileLength'])}</td>
          <td><a class="btn small" href="{e(download_url(mod, f))}">{t('Download', 'Скачать')}</a></td>
        </tr>""")

    shots = "".join(
        f'<a href="{e(s["url"])}" target="_blank" rel="noopener"><img src="{e(s.get("thumbnailUrl") or s["url"])}" '
        f'alt="{e(s.get("title") or mod["name"])}" loading="lazy"></a>'
        for s in mod.get("screenshots", []))

    tabs = []
    if guide:
        tabs.append(("guide", t("Guide", "Гайд")))
    tabs += [("about", t("Description", "Описание")), ("files", t("All versions", "Все версии"))]
    tab_nav = "".join(f'<a href="#{k}">{label}</a>' for k, label in tabs)

    guide_html = ""
    if guide:
        guide_html = f"""
  <section class="block" id="guide">
    <h2>{t('Guide', 'Гайд')}</h2>
    {render_guide(guide, 'en')}{render_guide(guide, 'ru')}
  </section>"""

    return f"""
  <a class="back" href="../../">{t('← All mods', '← Все моды')}</a>
  <section class="mod page-head">
    <img class="logo" src="{e(logo)}" alt="" width="128" height="128">
    <div class="mod-title">
      <h1>{e(mod['name'])}</h1>
      {bilingual('p', e(mod.get('summary', '')), e(summary_ru) if summary_ru else None, 'summary')}
      <ul class="tags">{tags}</ul>
      <dl class="meta">
        <div><dt>Minecraft</dt><dd>{e(', '.join(mc))}</dd></div>
        <div><dt>{t('Loader', 'Загрузчик')}</dt><dd>{e(', '.join(loaders))}</dd></div>
        <div><dt>{t('Downloads', 'Загрузки')}</dt><dd>{mod['downloadCount']:,}</dd></div>
        <div><dt>{t('Updated', 'Обновлён')}</dt><dd>{date(mod['dateModified'])}</dd></div>
      </dl>
      <div class="actions">
        {latest_button(mod, latest)}
        <a class="btn" href="{e(mod['links']['websiteUrl'])}" target="_blank" rel="noopener">CurseForge ↗</a>
      </div>
    </div>
  </section>
  {f'<div class="shots">{shots}</div>' if shots else ''}
  <nav class="tabs">{tab_nav}</nav>
  {guide_html}
  <section class="block" id="about">
    <h2>{t('Description', 'Описание')}</h2>
    {bilingual('div', description, description_ru, 'desc-body')}
  </section>
  <section class="block" id="files">
    <h2>{t('All versions', 'Все версии')}</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>{t('File', 'Файл')}</th><th>Minecraft</th><th>{t('Loader', 'Загрузчик')}</th>
          <th>{t('Type', 'Тип')}</th><th>{t('Date', 'Дата')}</th><th>{t('Size', 'Размер')}</th><th></th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
  </section>"""


SITE_URL = "https://grinthas.github.io/"
HOME_DESC = ("Моды для Minecraft от Grint: гайды, рецепты и все версии для скачивания. "
             "Minecraft mods by Grint: guides, recipes and downloads for every version.")


def page(template, root, title, nav, main, url=SITE_URL, desc=HOME_DESC):
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(os.path.join(HERE, "site", "style.css"), "rb") as f:
        css_version = hashlib.sha1(f.read()).hexdigest()[:10]  # сбрасывает кэш браузера при изменении стилей
    return (template.replace("{{TITLE}}", html.escape(title))
                    .replace("{{DESC}}", html.escape(desc))
                    .replace("{{URL}}", url)
                    .replace("{{CSSV}}", css_version)
                    .replace("{{ROOT}}", root)
                    .replace("{{NAV}}", nav)
                    .replace("{{MAIN}}", main)
                    .replace("{{PROFILE}}", PROFILE)
                    .replace("{{BUILT}}", built))


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build():
    ids = listed_ids()
    mods = [m for m in cf("/mods", body={"modIds": ids}) if m.get("status") == STATUS_APPROVED]
    mods.sort(key=lambda m: m["dateCreated"], reverse=True)

    with open(os.path.join(HERE, "site", "template.html"), encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(HERE, "site", "home.html"), encoding="utf-8") as f:
        home = f.read()

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    shutil.copy(os.path.join(HERE, "site", "style.css"), OUT)
    if os.path.isdir(ICONS):
        shutil.copytree(ICONS, os.path.join(OUT, "icons"))

    cards, data = [], []
    for mod in mods:
        files = files_of(mod["id"])
        description = cf(f"/mods/{mod['id']}/description")
        ru = russian(mod, description, stamp="--stamp" in sys.argv)
        data.append((mod, files, description, ru))
        cards.append(render_card(mod, files, ru))

    def nav(root):
        return "".join(f'<a href="{root}mods/{html.escape(m["slug"])}/">{html.escape(m["name"])}</a>' for m, *_ in data)

    write(os.path.join(OUT, "index.html"),
          page(template, "", "Grint — моды для Minecraft | Minecraft Mods", nav(""), home.replace("{{MODS}}", "".join(cards))))
    urls = [SITE_URL]
    for mod, files, description, ru in data:
        main = render_page(mod, files, description, ru, load_guide(mod["id"]))
        url = f"{SITE_URL}mods/{mod['slug']}/"
        urls.append(url)
        write(os.path.join(OUT, "mods", mod["slug"], "index.html"),
              page(template, "../../", f"{mod['name']} — мод для Minecraft | Grint", nav("../../"), main,
                   url, f"{mod['name']}: {mod.get('summary', '')} Гайд, рецепты и скачивание."))

    # для поисковиков: список страниц и разрешение их обходить
    write(os.path.join(OUT, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write(os.path.join(OUT, "robots.txt"), f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n")

    write(os.path.join(OUT, "mods.json"),
          json.dumps([{"id": m["id"], "name": m["name"], "url": m["links"]["websiteUrl"]} for m, *_ in data], indent=2))
    print(f"Собрано: {len(mods)} мод(ов) → {OUT}")


if __name__ == "__main__":
    build()
