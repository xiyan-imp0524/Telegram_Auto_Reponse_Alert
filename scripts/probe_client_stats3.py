import re

import httpx
from bs4 import BeautifulSoup

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
slug = "contributors-needed-record-first-person-household-task-videos-for-ai-training-latin-america"

r = httpx.get(
    f"https://www.workana.com/job/{slug}",
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
    timeout=30,
)
soup = BeautifulSoup(r.text, "html.parser")

# Find client stats section
for p in soup.find_all("p"):
    text = p.get_text(" ", strip=True)
    if any(
        k in text.lower()
        for k in ["published projects", "projects paid", "member since"]
    ):
        parent = p.parent
        print("P:", text)
        print("PARENT:", parent.get_text("\n", strip=True)[:300])
        print("HTML:", str(parent)[:500])
        print("---")

# Try common class names
for selector in [".client-profile", ".employer", ".user-profile", ".profile-stats", ".box-common"]:
    nodes = soup.select(selector)
    if nodes:
        print("SELECTOR", selector, len(nodes))
        print(nodes[0].get_text("\n", strip=True)[:400])
