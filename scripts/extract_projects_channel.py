import re

import httpx

js = httpx.get(
    "https://cf.wkncdn.com/static/assets/build/bundle.app.155624501.js",
    timeout=60,
).text

for pattern in [
    r"projects-\$\{[^}]+\}.{0,400}",
    r"channels\.projects[^;]{0,400}",
    r"projects-\"[^\"]+\".{0,400}",
    r"bind\(\"[^\"]+\"[^)]{0,120}\)",
]:
    hits = re.findall(pattern, js, re.S)
    if hits:
        print(f"\n=== {pattern[:50]} ===")
        for hit in hits[:6]:
            print(hit[:400])

# search projects channel bindings
idx = js.find("channels.projects")
while idx != -1:
    print("\nCTX:", js[idx : idx + 500])
    idx = js.find("channels.projects", idx + 1)
