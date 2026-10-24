"""Собирает статический сайт с модами из mods.txt в папку _site.

Нужен CF_API_KEY. Сайт двуязычный (EN/RU): строки интерфейса переключаются
кнопкой, описания модов берутся с CurseForge.

Русские описания лежат в translations/<id>.json вместе с sha1 английского
оригинала. Если оригинал на CurseForge изменился (или перевода нет), то при
заданном DEEPL_API_KEY перевод делается заново через DeepL и сохраняется,
иначе в русской версии показывается английский текст.
Флаг --stamp проставляет sha1 в переводах, где он пустой (после ручного перевода).
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from notify import HERE, STATUS_APPROVED, UA, cf, listed_ids

OUT = os.path.join(HERE, "_site")
TRANSLATIONS = os.path.join(HERE, "translations")
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


def deepl(texts, html_tags):
    key = os.environ["DEEPL_API_KEY"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    params = [("target_lang", "RU"), ("source_lang", "EN")] + [("text", x) for x in texts]
    if html_tags:
        params.append(("tag_handling", "html"))
    req = urllib.request.Request(f"https://{host}/v2/translate", data=urllib.parse.urlencode(params).encode(),
                                 headers={"Authorization": f"DeepL-Auth-Key {key}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [x["text"] for x in json.load(r)["translations"]]


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
    if not os.environ.get("DEEPL_API_KEY"):
        return None
    summary_ru, = deepl([mod.get("summary", "")], html_tags=False)
    description_ru, = deepl([description], html_tags=True)
    tr = {"source_sha1": sha, "summary": summary_ru, "description": description_ru}
    save_translation(path, tr)
    print(f"Переведено через DeepL: {mod['name']}")
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


def render_mod(mod, files, description, ru):
    e = html.escape
    summary_ru, description_ru = ru or (None, None)
    url = mod["links"]["websiteUrl"]
    logo = (mod.get("logo") or {}).get("url", "")
    tags = "".join(f"<li>{e(c['name'])}</li>" for c in mod["categories"])
    mc = sorted({v for f in files for v in f["gameVersions"] if re.match(r"\d", v)}, reverse=True)
    loaders = sorted({v for f in files for v in f["gameVersions"] if v in LOADERS})
    # основной файл, выбранный автором на CurseForge, иначе самый свежий
    latest = next((f for f in files if f["id"] == mod.get("mainFileId")), files[0] if files else None)

    rows = []
    for f in files:
        en, ru, cls = RELEASE.get(f["releaseType"], RELEASE[1])
        fmc = ", ".join(v for v in f["gameVersions"] if re.match(r"\d", v))
        floader = ", ".join(v for v in f["gameVersions"] if v in LOADERS)
        rows.append(f"""
        <tr>
          <td class="fname">{e(f['displayName'])}</td>
          <td>{e(fmc)}</td>
          <td>{e(floader)}</td>
          <td><span class="badge {cls}">{t(en, ru)}</span></td>
          <td class="num">{date(f['fileDate'])}</td>
          <td class="num">{size(f['fileLength'])}</td>
          <td><a class="btn small" href="{e(download_url(mod, f))}">{t('Download', 'Скачать')}</a></td>
        </tr>""")

    shots = "".join(
        f'<a href="{e(s["url"])}" target="_blank" rel="noopener"><img src="{e(s.get("thumbnailUrl") or s["url"])}" '
        f'alt="{e(s.get("title") or mod["name"])}" loading="lazy"></a>'
        for s in mod.get("screenshots", []))

    latest_btn = (f'<a class="btn primary" href="{e(download_url(mod, latest))}">'
                  f'{t("Download latest", "Скачать последнюю")}<small>{e(latest["displayName"])}</small></a>'
                  if latest else "")

    return f"""
  <section class="mod" id="{e(mod['slug'])}">
    <div class="mod-head">
      <img class="logo" src="{e(logo)}" alt="" width="112" height="112">
      <div class="mod-title">
        <h2>{e(mod['name'])}</h2>
        {bilingual('p', e(mod.get('summary', '')), e(summary_ru) if summary_ru else None, 'summary')}
        <ul class="tags">{tags}</ul>
        <dl class="meta">
          <div><dt>{t('Minecraft', 'Minecraft')}</dt><dd>{e(', '.join(mc))}</dd></div>
          <div><dt>{t('Loader', 'Загрузчик')}</dt><dd>{e(', '.join(loaders))}</dd></div>
          <div><dt>{t('Downloads', 'Загрузки')}</dt><dd>{mod['downloadCount']:,}</dd></div>
          <div><dt>{t('Updated', 'Обновлён')}</dt><dd>{date(mod['dateModified'])}</dd></div>
        </dl>
        <div class="actions">
          {latest_btn}
          <a class="btn" href="{e(url)}" target="_blank" rel="noopener">CurseForge ↗</a>
        </div>
      </div>
    </div>
    {f'<div class="shots">{shots}</div>' if shots else ''}
    <details class="desc">
      <summary>{t('Description', 'Описание')}</summary>
      {bilingual('div', description, description_ru, 'desc-body')}
    </details>
    <h3>{t('All versions', 'Все версии')}</h3>
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


def build():
    ids = listed_ids()
    mods = [m for m in cf("/mods", body={"modIds": ids}) if m.get("status") == STATUS_APPROVED]
    mods.sort(key=lambda m: m["dateCreated"], reverse=True)

    sections, nav = [], []
    for mod in mods:
        files = files_of(mod["id"])
        description = cf(f"/mods/{mod['id']}/description")
        ru = russian(mod, description, stamp="--stamp" in sys.argv)
        sections.append(render_mod(mod, files, description, ru))
        nav.append(f'<a href="#{html.escape(mod["slug"])}">{html.escape(mod["name"])}</a>')

    with open(os.path.join(HERE, "site", "template.html"), encoding="utf-8") as f:
        page = f.read()
    page = (page.replace("{{NAV}}", "".join(nav))
                .replace("{{MODS}}", "".join(sections))
                .replace("{{PROFILE}}", PROFILE)
                .replace("{{BUILT}}", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(OUT, "mods.json"), "w", encoding="utf-8") as f:
        json.dump([{"id": m["id"], "name": m["name"], "url": m["links"]["websiteUrl"]} for m in mods], f, indent=2)
    print(f"Собрано: {len(mods)} мод(ов) → {OUT}")


if __name__ == "__main__":
    build()
