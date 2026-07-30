import re

import httpx

js = httpx.get(
    "https://cf.wkncdn.com/static/assets/build/bundle.app.155624501.js",
    timeout=60,
).text

patterns = [
    r"Workana\.pusher.{0,300}",
    r"connectPusher.{0,800}",
    r"applicationKey.{0,120}",
    r"instant-notifications.{0,200}",
    r"savedSearch.{0,200}",
    r"notificationSettings.{0,200}",
]

for pattern in patterns:
    hits = re.findall(pattern, js, re.I | re.S)
    if hits:
        print(f"\n=== {pattern[:40]} ({len(hits)}) ===")
        for hit in hits[:2]:
            print(hit[:500])

# Find pusher key literal
for hit in re.findall(r'applicationKey:"([^"]+)"', js):
    print("\nPUSHER KEY:", hit)

for hit in re.findall(r"cluster:\"([^\"]+)\"", js):
    print("PUSHER CLUSTER:", hit)
