# CurseForge → Discord

Раз в час GitHub Actions запускает `notify.py`: моды из `mods.txt`, которые одобрены на CurseForge
и ещё не записаны в `sent.json`, отправляются в Discord (название, ссылка, описание, логотип).

Новый мод: допишите его Project ID в `mods.txt` и закоммитьте.

Secrets репозитория: `CF_API_KEY`, `DISCORD_WEBHOOK_URL`.
Ручной запуск: Actions → CurseForge -> Discord → Run workflow.
