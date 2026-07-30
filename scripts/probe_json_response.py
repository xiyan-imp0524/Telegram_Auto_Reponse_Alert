import html
import json
import re

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

r = httpx.get(
    "https://www.workana.com/en/jobs?category=it-programming&page=1",
    headers=HEADERS,
    follow_redirects=True,
    timeout=30,
)
print("status", r.status_code, "content-type", r.headers.get("content-type"))
text = r.text
print("first 200:", repr(text[:200]))

try:
    data = r.json()
    print("json top keys", data.keys() if isinstance(data, dict) else type(data))
    print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print("not json", e)
    m = re.search(r":results-initials='(\{.*?\})'", text, re.S)
    if m:
        payload = json.loads(html.unescape(m.group(1)))
        print("embedded results", len(payload.get("results", [])))
