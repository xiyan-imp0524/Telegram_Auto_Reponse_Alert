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
for sel in [".client-info", ".employer-info", ".profile-name", ".user-name", ".media-heading", "aside", ".sidebar"]:
    nodes = soup.select(sel)
    if nodes:
        print(sel, "->", nodes[0].get_text("\n", strip=True)[:200])

# employer box near stats
for div in soup.select("div.item-data"):
    parent = div.parent
    if parent:
        print("BLOCK:", parent.get_text("\n", strip=True)[:300])
        break
