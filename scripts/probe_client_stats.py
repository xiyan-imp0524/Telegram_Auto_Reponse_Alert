import html
import json
import re

import httpx

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
slug = "contributors-needed-record-first-person-household-task-videos-for-ai-training-latin-america"

r = httpx.get(
    f"https://www.workana.com/job/{slug}",
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
    timeout=30,
)

for pattern in [
    r"Member since[^<]{0,200}",
    r"memberSince.{0,120}",
    r"publishedProjects.{0,120}",
    r"paymentsCount.{0,120}",
    r"clientLeftPanel.{0,3000}",
]:
    match = re.search(pattern, r.text, re.I | re.S)
    if match:
        print("===", pattern[:30], "===")
        print(match.group(0)[:800])
        print()

# HTML member since block
match = re.search(
    r"(Member since|miembro desde|Membro desde)[^<]*</[^>]+>[^<]*<[^>]+>([^<]+)",
    r.text,
    re.I,
)
if match:
    print("HTML member:", match.groups())

# Search for stats list items
for match in re.finditer(r"<li[^>]*>.*?projects?.*?</li>", r.text, re.I | re.S):
    print("LI:", re.sub(r"\s+", " ", match.group(0))[:200])

# initial/vue data
for match in re.finditer(r":initials?='(\{.*?\})'", r.text, re.S):
    try:
        data = json.loads(html.unescape(match.group(1)))
        text = json.dumps(data)
        if any(k in text.lower() for k in ["member", "payment", "publish", "client"]):
            print("INITIALS keys:", list(data.keys()) if isinstance(data, dict) else type(data))
            print(text[:2000])
    except Exception:
        pass
