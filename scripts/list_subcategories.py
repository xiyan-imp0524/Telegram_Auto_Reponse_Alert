"""List IT & Programming subcategories from Workana."""
import json
import re

import httpx

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
r = httpx.get(
    "https://www.workana.com/en/jobs?category=it-programming",
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
    timeout=30,
    follow_redirects=True,
)
# search-filters payload contains subcategories mapping
m = re.search(r'search-filters :payload="(\{.*?\})"', r.text, re.S)
if not m:
    m = re.search(r":payload='(\{.*?\})'\s", r.text, re.S)
if m:
    import html as h

    raw = h.unescape(m.group(1))
    data = json.loads(raw)
    subs = data.get("mappings", {}).get("subcategories", {})
    cats = data.get("mappings", {}).get("categories", {})
    print("category it-programming:", cats.get("it-programming", cats))
    print("\nSubcategories:")
    for slug, label in sorted(subs.items(), key=lambda x: x[1])[:30]:
        if "program" in slug or "web" in slug or "data" in slug or "app" in slug or "e-" in slug or "word" in slug or "art" in slug or "desk" in slug or "other" in slug:
            print(f"  {slug} -> {label}")
    print(f"\nTotal subcategories in mappings: {len(subs)}")
    # print all that belong to it-programming - need to find filter structure
    filters = data.get("filters", {})
    print("\nfilter keys:", list(filters.keys())[:20])
