# Grint — моды для Minecraft

Сайт: https://grinthas.github.io

Раз в час (и при каждом push) GitHub Actions:
- `notify.py` отправляет в Discord моды из `mods.txt`, которые одобрены на CurseForge
  и ещё не записаны в `sent.json` (название, ссылка, описание, логотип);
- `build_site.py` собирает сайт по шаблону `site/template.html` (все версии файлов,
  скриншоты, описание, ссылка на CurseForge) и публикует его на GitHub Pages.

Новый мод: допишите его Project ID в `mods.txt` и закоммитьте.

Русские описания: `translations/<id>.json`. Если описание на CurseForge изменилось,
перевод автоматически обновляется через DeepL (если задан `DEEPL_API_KEY`),
иначе на русской версии сайта показывается английский текст.
После ручной правки перевода очистите `source_sha1` и запустите `python build_site.py --stamp`.

Secrets репозитория: `CF_API_KEY`, `DISCORD_WEBHOOK_URL`, необязательный `DEEPL_API_KEY`.
Ручной запуск: Actions → CurseForge -> Discord + site → Run workflow.
