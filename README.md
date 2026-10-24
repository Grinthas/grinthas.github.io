# Grint — моды для Minecraft

Сайт: https://grinthas.github.io

Раз в час (и при каждом push) GitHub Actions:
- `notify.py` отправляет в Discord моды из `mods.txt`, которые одобрены на CurseForge
  и ещё не записаны в `sent.json` (название, ссылка, описание, логотип);
- `build_site.py` собирает сайт по шаблону `site/template.html` (все версии файлов,
  скриншоты, описание, ссылка на CurseForge) и публикует его на GitHub Pages.

Новый мод: допишите его Project ID в `mods.txt` и закоммитьте.

Русские описания: `translations/<id>.json`. Если описание на CurseForge изменилось,
перевод автоматически делается заново через GitHub Models (бесплатно, токен Actions,
ключ не нужен). Если GitHub Models недоступен, на русской версии временно показывается
английский текст, а перевод повторится при следующей сборке.
После ручной правки перевода очистите `source_sha1` и запустите `python build_site.py --stamp`.

Secrets репозитория: `CF_API_KEY`, `DISCORD_WEBHOOK_URL`.
Ручной запуск: Actions → CurseForge -> Discord + site → Run workflow.
