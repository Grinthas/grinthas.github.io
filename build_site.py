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


UPCOMING = os.path.join(HERE, "upcoming")

# Комментарии и предложения: giscus, хранит их в Discussions этого репозитория (вход через GitHub)
GISCUS_REPO, GISCUS_REPO_ID = "Grinthas/grinthas.github.io", "R_kgDOVVtnrg"
COMMENTS_CATEGORY = ("General", "DIC_kwDOVVtnrs4DJgn8")
IDEAS_CATEGORY = ("Ideas", "DIC_kwDOVVtnrs4DJgn-")
# Google Форма для предложений без регистрации (ответы видит только владелец формы).
# Своя форма в стиле сайта шлёт ответы прямо в неё; entry.* — номера полей Google Формы,
# а варианты мода должны совпадать с вариантами в самой форме, иначе Google отклонит ответ.
SUGGEST_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdQb0cwp2ciF2dtAmVmpB6cQ6U4jc4YdmGng_qoEhiOFTlo2Q/formResponse"
FORM_NICK, FORM_MOD, FORM_TEXT = "entry.93182872", "entry.1433504158", "entry.1926191801"
FORM_MODS = ["AutomaticSpawner", "AE2 Crafting CPU Box", "Molten Industry", "ExtremeAe2Assembler", "Grint Guide", "Recipe Editor", "Предложить новый мод"]


def suggest_form():
    options = "".join(f'<option>{html.escape(m)}</option>' for m in FORM_MODS)
    return f"""
    <form class="suggest-form" id="suggest">
      <label>{t('Nickname (optional)', 'Ник (необязательно)')}<input name="{FORM_NICK}" maxlength="60"></label>
      <label>{t('Which mod?', 'Для какого мода?')}<select name="{FORM_MOD}" required>{options}</select></label>
      <label>{t('Your suggestion', 'Ваше предложение')}<textarea name="{FORM_TEXT}" rows="6" required></textarea></label>
      <button class="btn primary" type="submit">{t('Send', 'Отправить')}</button>
      <p class="sent" hidden>{t('Thanks! Your suggestion has been sent.', 'Спасибо! Предложение отправлено.')}</p>
    </form>
    <script>
      document.getElementById("suggest").addEventListener("submit", function (e) {{
        e.preventDefault();
        var f = e.target, btn = f.querySelector("button");
        btn.disabled = true;
        // Google не отдаёт ответ чужому сайту (no-cors), поэтому считаем отправку успешной
        fetch("{SUGGEST_FORM}", {{method: "POST", mode: "no-cors", body: new FormData(f)}})
          .then(function () {{ f.reset(); f.querySelector(".sent").hidden = false; }})
          .finally(function () {{ btn.disabled = false; }});
      }});
    </script>"""


def giscus(category, term):
    """Ветка обсуждения giscus; язык виджета следует за переключателем EN/RU."""
    name, cid = category
    return f"""
    <div class="giscus"></div>
    <script>
      (function () {{
        var s = document.createElement("script");
        s.src = "https://giscus.app/client.js";
        var cfg = {{repo: "{GISCUS_REPO}", "repo-id": "{GISCUS_REPO_ID}", category: "{html.escape(name)}",
          "category-id": "{cid}", mapping: "specific", term: "{html.escape(term)}", strict: "1",
          "reactions-enabled": "1", "emit-metadata": "0", "input-position": "top",
          theme: "preferred_color_scheme", lang: document.documentElement.lang, loading: "lazy"}};
        for (var k in cfg) s.setAttribute("data-" + k, cfg[k]);
        s.crossOrigin = "anonymous"; s.async = true;
        document.currentScript.parentNode.appendChild(s);
        document.querySelectorAll(".lang button").forEach(function (b) {{
          b.addEventListener("click", function () {{
            var f = document.querySelector("iframe.giscus-frame");
            if (f) f.contentWindow.postMessage({{giscus: {{setConfig: {{lang: b.dataset.lang}}}}}}, "https://giscus.app");
          }});
        }});
      }})();
    </script>"""


def comments_section(term):
    return f"""
  <section class="block" id="comments">
    <h2>{t('Comments', 'Комментарии')}</h2>
    <p class="hint">{t('Sign in with GitHub to comment.', 'Чтобы оставить комментарий, войдите через GitHub.')}</p>
    {giscus(COMMENTS_CATEGORY, term)}
  </section>"""


def render_suggestions():
    return f"""
  <a class="back" href="../">{t('← All mods', '← Все моды')}</a>
  <section class="hero">
    <h1>{t('Suggestions', 'Предложения')}</h1>
    <p>{t('Ideas for new mods, machines and features. Write your suggestion below or vote for others with a reaction.',
          'Идеи новых модов, машин и функций. Напишите своё предложение ниже или поддержите чужое реакцией.')}</p>
    <div class="actions"><a class="btn" href="https://github.com/{GISCUS_REPO}/discussions/categories/ideas" target="_blank" rel="noopener">{t('All suggestions on GitHub ↗', 'Все предложения на GitHub ↗')}</a></div>
  </section>
  <section class="block" id="form">
    <h2>{t('Suggest without signing up', 'Предложить без регистрации')}</h2>
    <p class="hint">{t('Only Grint sees these suggestions.', 'Такие предложения видит только Grint.')}</p>
    {suggest_form()}
  </section>
  <section class="block" id="github">
    <h2>{t('Public suggestions (GitHub account)', 'Открытые предложения (через GitHub)')}</h2>
    {giscus(IDEAS_CATEGORY, "suggestions")}
  </section>"""


def load_upcoming(released):
    """Моды из upcoming/*.json, которых ещё нет среди одобренных на CurseForge.
    Совпадение — по cf_id или по названию: как только мод одобрят, его карточка
    сама сменится на настоящую (со ссылкой на CurseForge и файлами)."""
    ids = {m["id"] for m in released}
    names = {m["name"].lower() for m in released}
    out = []
    for name in sorted(os.listdir(UPCOMING)) if os.path.isdir(UPCOMING) else []:
        if not name.endswith(".json"):
            continue
        with open(os.path.join(UPCOMING, name), encoding="utf-8") as f:
            u = json.load(f)
        if u.get("cf_id") in ids or u["name"].lower() in names:
            continue
        out.append(u)
    return out


def upcoming_logo(u):
    """Адрес логотипа с версией: после замены картинки браузер не покажет старую из кэша."""
    with open(os.path.join(UPCOMING, u["logo"]), "rb") as f:
        return f"upcoming/{html.escape(u['logo'])}?v={hashlib.sha1(f.read()).hexdigest()[:8]}"


def soon_badge():
    return f'<span class="btn soon">{t("Coming soon to CurseForge", "Скоро на CurseForge")}</span>'


def render_upcoming_card(u):
    e = html.escape
    page = f"mods/{e(u['slug'])}/"
    tags = "".join(f"<li>{e(c)}</li>" for c in u["tags"])
    return f"""
  <article class="mod card">
    <a href="{page}"><img class="logo" src="{upcoming_logo(u)}" alt="" width="96" height="96"></a>
    <div class="mod-title">
      <h2><a href="{page}">{e(u['name'])}</a></h2>
      {bilingual('p', e(u['summary']['en']), e(u['summary']['ru']), 'summary')}
      <ul class="tags">{tags}</ul>
      <p class="facts">Minecraft {e(u['minecraft'])} · {e(u['loader'])}</p>
      <div class="actions">
        <a class="btn" href="{page}">{t('Details →', 'Подробнее →')}</a>
        {soon_badge()}
      </div>
    </div>
  </article>"""


def render_upcoming_page(u):
    e = html.escape
    tags = "".join(f"<li>{e(c)}</li>" for c in u["tags"])
    return f"""
  <a class="back" href="../../">{t('← All mods', '← Все моды')}</a>
  <section class="mod page-head">
    <img class="logo" src="../../{upcoming_logo(u)}" alt="" width="128" height="128">
    <div class="mod-title">
      <h1>{e(u['name'])}</h1>
      {bilingual('p', e(u['summary']['en']), e(u['summary']['ru']), 'summary')}
      <ul class="tags">{tags}</ul>
      <dl class="meta">
        <div><dt>Minecraft</dt><dd>{e(u['minecraft'])}</dd></div>
        <div><dt>{t('Loader', 'Загрузчик')}</dt><dd>{e(u['loader'])}</dd></div>
      </dl>
      <div class="actions">{soon_badge()}</div>
    </div>
  </section>
  <section class="block" id="about">
    <h2>{t('Description', 'Описание')}</h2>
    {bilingual('div', u['description']['en'], u['description']['ru'], 'desc-body')}
  </section>
  {comments_section(u['slug'])}"""


MODPACKS = os.path.join(HERE, "modpacks")


def load_modpacks():
    """Сборки из modpacks/*.json: карточка на вкладке «Сборки» и своя страница с трейлером."""
    out = []
    for name in sorted(os.listdir(MODPACKS)) if os.path.isdir(MODPACKS) else []:
        if name.endswith(".json"):
            with open(os.path.join(MODPACKS, name), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def pack_file(p, key):
    """Адрес файла сборки с версией, чтобы после замены браузер не показывал старый из кэша."""
    with open(os.path.join(MODPACKS, p[key]), "rb") as f:
        return f"modpacks/{html.escape(p[key])}?v={hashlib.sha1(f.read()).hexdigest()[:8]}"


def pack_link(p):
    if p.get("cf_url"):
        return f'<a class="btn primary" href="{html.escape(p["cf_url"])}" target="_blank" rel="noopener">CurseForge ↗</a>'
    return soon_badge()


def render_pack_card(p, root):
    e = html.escape
    page = f"{root}modpacks/{e(p['slug'])}/"
    tags = "".join(f"<li>{e(c)}</li>" for c in p["tags"])
    return f"""
  <article class="mod card">
    <a href="{page}"><img class="logo" src="{root}{pack_file(p, 'logo')}" alt="" width="96" height="96"></a>
    <div class="mod-title">
      <h2><a href="{page}">{e(p['name'])}</a></h2>
      {bilingual('p', e(p['summary']['en']), e(p['summary']['ru']), 'summary')}
      <ul class="tags">{tags}</ul>
      <p class="facts">Minecraft {e(p['minecraft'])} · {e(p['loader'])}</p>
      <div class="actions">
        <a class="btn" href="{page}">{t('Details →', 'Подробнее →')}</a>
        {pack_link(p)}
      </div>
    </div>
  </article>"""


def render_packs_index(packs):
    cards = "".join(render_pack_card(p, "../") for p in packs) or (
        f'<p class="empty">{t("New modpacks are coming soon.", "Новые сборки скоро появятся.")}</p>')
    return f"""
  <section class="hero">
    <h1>{t('Modpacks by Grint', 'Сборки от Grint')}</h1>
    <p>{t('Our own modpacks with a story, quests and mods made for them.',
          'Наши собственные сборки: с сюжетом, квестами и модами, сделанными специально для них.')}</p>
  </section>
  {cards}"""


def render_pack_page(p):
    e = html.escape
    tags = "".join(f"<li>{e(c)}</li>" for c in p["tags"])
    video = ""
    if p.get("video"):
        video = f"""
  <section class="block trailer">
    <h2>{t('Trailer', 'Трейлер')}</h2>
    <video controls preload="metadata" playsinline poster="../../{pack_file(p, 'poster')}" src="../../{pack_file(p, 'video')}"></video>
  </section>"""
    return f"""
  <a class="back" href="../">{t('← All modpacks', '← Все сборки')}</a>
  <section class="mod page-head">
    <img class="logo" src="../../{pack_file(p, 'logo')}" alt="" width="128" height="128">
    <div class="mod-title">
      <h1>{e(p['name'])}</h1>
      {bilingual('p', e(p['summary']['en']), e(p['summary']['ru']), 'summary')}
      <ul class="tags">{tags}</ul>
      <dl class="meta">
        <div><dt>Minecraft</dt><dd>{e(p['minecraft'])}</dd></div>
        <div><dt>{t('Loader', 'Загрузчик')}</dt><dd>{e(p['loader'])}</dd></div>
      </dl>
      <div class="actions">{pack_link(p)}</div>
    </div>
  </section>{video}
  <section class="block" id="about">
    <h2>{t('Description', 'Описание')}</h2>
    {bilingual('div', p['description']['en'], p['description']['ru'], 'desc-body')}
  </section>
  {comments_section('modpack-' + p['slug'])}"""


def write_modpacks(template, nav, urls):
    """Вкладка «Сборки» и страница каждой сборки; файлы (логотип, видео) копируются рядом."""
    packs = load_modpacks()
    if os.path.isdir(MODPACKS):
        shutil.copytree(MODPACKS, os.path.join(OUT, "modpacks"), ignore=shutil.ignore_patterns("*.json"), dirs_exist_ok=True)
    write(os.path.join(OUT, "modpacks", "index.html"),
          page(template, "../", "Сборки | Modpacks — Grint", nav("../"), render_packs_index(packs),
               f"{SITE_URL}modpacks/", "Сборки Minecraft от Grint. Minecraft modpacks by Grint."))
    urls.append(f"{SITE_URL}modpacks/")
    for p in packs:
        url = f"{SITE_URL}modpacks/{p['slug']}/"
        urls.append(url)
        write(os.path.join(OUT, "modpacks", p["slug"], "index.html"),
              page(template, "../../", f"{p['name']} — сборка Minecraft | Grint", nav("../../"), render_pack_page(p),
                   url, f"{p['name']}: {p['summary']['ru']}"))


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


def changelog(mod_id, file_id):
    """Changelog файла с CurseForge (HTML) или пустая строка, если его нет."""
    try:
        return (cf(f"/mods/{mod_id}/files/{file_id}/changelog") or "").strip()
    except Exception as e:
        print(f"Changelog {mod_id}/{file_id} недоступен: {e}")
        return ""


def changelog_ru(file_id, text):
    """Русский changelog: из translations/changelog/<file id>.json, иначе машинный перевод (как у описаний)."""
    path = os.path.join(TRANSLATIONS, "changelog", f"{file_id}.json")
    sha = hashlib.sha1(text.encode("utf-8")).hexdigest()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            tr = json.load(f)
        if tr["source_sha1"] == sha:
            return tr["changelog"]
    if not os.environ.get("AUTO_TRANSLATE"):
        return None
    try:
        ru = translate(text, is_html=True)
    except Exception as e:
        print(f"Не удалось перевести changelog {file_id}: {e}")
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_translation(path, {"source_sha1": sha, "changelog": ru, "machine": True})
    return ru


def render_changes(mod, files):
    """Вкладка «Изменения»: что нового в каждой версии, новые сверху."""
    e = html.escape
    items = []
    for f in files:
        en, ru_, cls = RELEASE.get(f["releaseType"], RELEASE[1])
        text = changelog(mod["id"], f["id"])
        if re.sub(r"<[^>]+>|&nbsp;|\s", "", text):
            body = bilingual("div", text, changelog_ru(f["id"], text), "desc-body")
        else:
            body = f'<p class="hint">{t("No changelog for this version.", "Для этой версии нет списка изменений.")}</p>'
        items.append(f"""
      <article class="change">
        <h3>{e(f['displayName'])} <span class="badge {cls}">{t(en, ru_)}</span> <span class="date">{date(f['fileDate'])}</span></h3>
        {body}
      </article>""")
    return "".join(items)


def description_images(description):
    """Картинки из описания: замена галереи, если на CurseForge её не заполнили."""
    urls = re.findall(r'<img[^>]+src="([^"]+)"', description or "")
    return [{"url": html.unescape(u)} for u in dict.fromkeys(urls)
            if not re.search(r"badge|shields\.io|\.svg", u)]


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
        for s in mod.get("screenshots") or description_images(description))

    tabs = []
    if guide:
        tabs.append(("guide", t("Guide", "Гайд")))
    tabs += [("about", t("Description", "Описание")), ("changes", t("Changelog", "Изменения")),
             ("files", t("All versions", "Все версии")),
             ("comments", t("Comments", "Комментарии"))]
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
  <section class="block" id="changes">
    <h2>{t('Changelog', 'Изменения')}</h2>
    {render_changes(mod, files)}
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
  </section>
  {comments_section(mod['slug'])}"""


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

    upcoming = load_upcoming(mods)
    if upcoming:
        shutil.copytree(UPCOMING, os.path.join(OUT, "upcoming"), ignore=shutil.ignore_patterns("*.json"))
    cards += [render_upcoming_card(u) for u in upcoming]

    def nav(root):
        return "".join(f'<a href="{root}mods/{html.escape(s)}/">{html.escape(n)}</a>'
                       for s, n in [(m["slug"], m["name"]) for m, *_ in data] + [(u["slug"], u["name"]) for u in upcoming])

    write(os.path.join(OUT, "index.html"),
          page(template, "", "Grint — моды для Minecraft | Minecraft Mods", nav(""), home.replace("{{MODS}}", "".join(cards))))
    urls = [SITE_URL, f"{SITE_URL}suggestions/"]
    write(os.path.join(OUT, "suggestions", "index.html"),
          page(template, "../", "Предложения | Suggestions — Grint", nav("../"), render_suggestions(),
               f"{SITE_URL}suggestions/", "Предложения идей для модов Grint. Suggestions for Grint mods."))
    for u in upcoming:
        url = f"{SITE_URL}mods/{u['slug']}/"
        urls.append(url)
        write(os.path.join(OUT, "mods", u["slug"], "index.html"),
              page(template, "../../", f"{u['name']} — мод для Minecraft | Grint", nav("../../"), render_upcoming_page(u),
                   url, f"{u['name']}: {u['summary']['en']} Скоро на CurseForge."))
    write_modpacks(template, nav, urls)
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
