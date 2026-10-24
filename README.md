# Grint — моды для Minecraft

Сайт: https://grinthas.github.io

Раз в час (и при каждом push) GitHub Actions:
- `notify.py` отправляет в Discord моды из `mods.txt`, которые одобрены на CurseForge
  и ещё не записаны в `sent.json` (название, ссылка, описание, логотип);
- `build_site.py` собирает сайт и публикует его на GitHub Pages: главная со списком модов
  (`site/home.html`) и страница каждого мода `mods/<slug>/` с гайдом, скриншотами,
  описанием и всеми версиями файлов. Оформление: `site/template.html`, `site/style.css`.

## Новый мод

Откройте https://github.com/Grinthas/grinthas.github.io/edit/main/mods.txt, допишите строку
с Project ID (страница мода на CurseForge → About Project → Project ID) и нажмите
**Commit changes**. Мод появится на сайте и в Discord, как только CurseForge его одобрит.

## Гайды

`guides/<project id>.json` создаёт `tools/import_guides.py` из внутриигрового гайда
(`C:\mods\grintguide`) и lang/рецептов мода. После изменения гайда запустите локально
`py tools/import_guides.py`, затем `py tools/import_icons.py` (иконки предметов из jar-файлов
Minecraft и модов в `guides/icons/`) и закоммитьте `guides/`. Для нового мода добавьте его в `MODS`
в начале скрипта.

Главы только для сайта (которых нет во внутриигровом гайде) лежат в `guides/extra/<project id>.json`
и вставляются в гайд при импорте (`insert_at` — номер позиции главы). Так добавлена
«Творческая кузня» для Molten Industry.

## Русские описания

`translations/<id>.json`. Если описание на CurseForge изменилось,
перевод автоматически делается заново офлайн через Argos Translate (бесплатно, без ключей;
качество машинное, такие переводы помечены `"machine": true` — их можно заменить ручными).
Если перевод не удался, на русской версии временно показывается английский текст,
а перевод повторится при следующей сборке.
После ручной правки перевода очистите `source_sha1` и запустите `python build_site.py --stamp`.

Secrets репозитория: `CF_API_KEY`, `DISCORD_WEBHOOK_URL`.
Ручной запуск: Actions → CurseForge -> Discord + site → Run workflow.
