import json, os, urllib.request, urllib.error

for model in ("openai/gpt-4o-mini", "openai/gpt-4.1-mini"):
    for ver in (None, "2026-03-10", "2022-11-28"):
        h = {"Authorization": f"Bearer {os.environ['MODELS_TOKEN']}", "Content-Type": "application/json",
             "Accept": "application/vnd.github+json", "User-Agent": "probe"}
        if ver:
            h["X-GitHub-Api-Version"] = ver
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Say hi in Russian"}]}).encode()
        req = urllib.request.Request("https://models.github.ai/inference/chat/completions", data=body, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(model, ver, r.status, r.headers.get("Content-Type"), r.read()[:300])
        except urllib.error.HTTPError as e:
            print(model, ver, e.code, e.read()[:300])
