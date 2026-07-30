import re

import httpx

js = httpx.get(
    "https://cf.wkncdn.com/static/assets/build/bundle.app.155624501.js",
    timeout=60,
).text

# Find Workana.pusher config object in bundle
for hit in re.findall(r'pusher:\{[^\}]{0,500}\}', js):
    print("PUSHER CONFIG:", hit[:500])

for hit in re.findall(r'authEndpoint:"([^"]+)"', js):
    print("AUTH ENDPOINT:", hit)

for hit in re.findall(r'channel:"([^"]+)"', js):
    if "private" in hit or "presence" in hit or "notification" in hit:
        print("CHANNEL:", hit)

# notificationEventByLanguage full function snippet
m = re.search(r"notificationEventByLanguage\(e\)\{.{0,1200}?\}\}", js)
if m:
    print("\nFUNCTION:\n", m.group(0)[:1200])
