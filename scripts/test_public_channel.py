"""Test public projects-en Pusher channel only."""
import time

import pysher

events = []

pusher = pysher.Pusher("5d14500e05a938842a18", secure=True)
pusher.connection.bind("pusher:connection_established", lambda d: print("connected"))
projects = pusher.subscribe("projects-en")
projects.bind("pusher:subscription_succeeded", lambda _: print("projects-en OK"))
projects.bind("pusher:subscription_error", lambda d: print("projects-en ERR", d))
projects.bind("added", lambda e: print("ADDED", e))


def on_any(name):
    def handler(data):
        print("event", name, str(data)[:300])

    return handler


for evt in ["added", "updated", "removed", "project_added", "new_project"]:
    projects.bind(evt, on_any(evt))

print("listening 20s...")
pusher.connect()
time.sleep(20)
pusher.disconnect()
