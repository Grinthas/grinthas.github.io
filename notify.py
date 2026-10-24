"""Отправляет в Discord новые моды автора с CurseForge.

Переменные окружения:
  CF_API_KEY           ключ CurseForge API (console.curseforge.com)
  DISCORD_WEBHOOK_URL  URL вебхука Discord
  CF_AUTHOR            имя автора на CurseForge (по умолчанию Grint)

Источник модов:
  1. mods.txt — Project ID по одному на строку (# — комментарий).
  2. Поиск /mods/search по authorId, если ключу он доступен (сейчас 403,
     тогда тихо пропускается). authorId берётся из первого мода в mods.txt.

Мод отправляется, только когда он одобрен (status 4) и ещё не в sent.json.
Флаг --dry-run печатает, что было бы отправлено, ничего не меняя.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.curseforge.com/v1"
GAME_MINECRAFT = 432
STATUS_APPROVED = 4
UA = "curseforge-discord-notifier"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "sent.json")
MODS_TXT = os.path.join(HERE, "mods.txt")


def cf(path, params=None, body=None):
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={
        "x-api-key": os.environ["CF_API_KEY"],
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


def listed_ids():
    ids = []
    with open(MODS_TXT, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                ids.append(int(line))
    return ids


def searched_ids(author_id):
    ids, index = [], 0
    try:
        while True:
            page = cf("/mods/search", {"gameId": GAME_MINECRAFT, "authorId": author_id,
                                       "index": index, "pageSize": 50})
            ids += [m["id"] for m in page]
            index += len(page)
            if len(page) < 50:
                return ids
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
        return ids


def send(mod):
    url = mod["links"]["websiteUrl"]
    embed = {
        "title": mod["name"],
        "url": url,
        "description": mod.get("summary", ""),
        "color": 0xF16436,
        "footer": {"text": "CurseForge"},
    }
    logo = (mod.get("logo") or {}).get("url")
    if logo:
        embed["image"] = {"url": logo}
    body = json.dumps({"content": f"Новый мод: **{mod['name']}**\n{url}", "embeds": [embed]}).encode()
    req = urllib.request.Request(os.environ["DISCORD_WEBHOOK_URL"], data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=30).close()
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        time.sleep(float(json.load(e).get("retry_after", 2)) + 0.5)
        urllib.request.urlopen(req, timeout=30).close()


def save(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    dry = "--dry-run" in sys.argv
    author = os.environ.get("CF_AUTHOR", "Grint").lower()
    state = {"sent": []}
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            state = json.load(f)

    ids = listed_ids()
    mods = cf("/mods", body={"modIds": ids}) if ids else []
    author_id = next((a["id"] for m in mods for a in m["authors"] if a["name"].lower() == author), None)
    if author_id:
        extra = [i for i in searched_ids(author_id) if i not in ids]
        if extra:
            mods += cf("/mods", body={"modIds": extra})

    new = [m for m in mods
           if m["id"] not in state["sent"]
           and m.get("status") == STATUS_APPROVED
           and any(a["name"].lower() == author for a in m["authors"])]
    for mod in new:
        print(f"{'[dry-run] ' if dry else ''}Отправляю: {mod['name']} ({mod['id']}) {mod['links']['websiteUrl']}")
        if dry:
            continue
        send(mod)
        state["sent"].append(mod["id"])
        save(state)  # сразу, чтобы при сбое на следующем моде не было дублей
        time.sleep(1)
    if not new:
        print("Новых модов нет")


if __name__ == "__main__":
    main()
