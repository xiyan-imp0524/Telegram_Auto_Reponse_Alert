import re

import httpx

page = httpx.get(
    "https://www.workana.com/en/jobs?category=it-programming",
    headers={"User-Agent": "Mozilla/5.0"},
    follow_redirects=True,
    timeout=30,
).text

scripts = re.findall(
    r'src="(https://cf\.wkncdn\.com/static/assets/build/[^"]+\.js)"',
    page,
)
print("scripts", len(scripts))
for src in scripts:
    print(" ", src.split("/")[-1])

# also check mfe import map
for m in re.findall(r'href="(https://cf\.wkncdn\.com/[^"]+)"', page):
    if "importmap" in m or "mfe" in m:
        print("link", m)
