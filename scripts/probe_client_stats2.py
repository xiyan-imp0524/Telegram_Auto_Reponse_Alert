import re

import httpx

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
slug = "contributors-needed-record-first-person-household-task-videos-for-ai-training-latin-america"

r = httpx.get(
    f"https://www.workana.com/job/{slug}",
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
    timeout=30,
)

# dump lines with interesting keywords
keywords = [
    "member since",
    "payment",
    "published",
    "project",
    "client",
    "employer",
    "rating",
    "verified",
]
for line in r.text.splitlines():
    lower = line.lower()
    if any(k in lower for k in keywords) and len(line) < 500:
        if any(x in lower for x in ["member since", "payments", "published", "projects published", "projects paid"]):
            print(line.strip()[:300])
