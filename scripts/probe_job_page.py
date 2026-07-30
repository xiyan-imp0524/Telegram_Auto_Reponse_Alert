"""Probe Workana job page for client/employer stats."""
import json
import re

import httpx

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
slug = "contributors-needed-record-first-person-household-task-videos-for-ai-training-latin-america"

r = httpx.get(
    f"https://www.workana.com/job/{slug}",
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
    follow_redirects=True,
    timeout=30,
)
print("status", r.status_code, "len", len(r.text))

patterns = [
    r"member since|miembro desde|membro desde",
    r"projects? published|proyectos? publicados|projetos? publicados",
    r"payments? made|pagos? realizados|pagamentos?",
    r"publishedProjects|paymentsCount|memberSince|clientSince",
    r"employer[^\"]{0,80}",
    r"popoverContent[^\"]{0,200}",
    r"client[^\"]{0,100}",
    r"Workana\.[a-zA-Z]+\s*=\s*\{",
]
text = r.text.lower()
for p in patterns:
    hits = re.findall(p, r.text, re.I)
    if hits:
        print(f"\n{p[:40]}: {len(hits)}")
        for h in hits[:3]:
            print(" ", str(h)[:200])

# save snippet around interesting terms
for term in ["member", "payment", "published", "client", "employer"]:
    idx = text.find(term)
    if idx != -1:
        print(f"\n--- context for '{term}' ---")
        print(r.text[max(0, idx - 50) : idx + 250])
