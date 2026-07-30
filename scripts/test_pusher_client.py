"""Test Pusher client connects and subscribes."""
import logging
import time

from workana.pusher_client import WorkanaPusherClient, WorkanaSession

logging.basicConfig(level=logging.INFO)

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"


def on_added(payload):
    print("PROJECT ADDED:", payload)


def on_notification(payload):
    print("NOTIFICATION:", str(payload)[:500])


session = WorkanaSession.from_cookie(SESSION, language="en")
print("projects channel:", session.projects_channel)
print("notification channel:", session.notification_channel)

client = WorkanaPusherClient(
    session,
    on_project_added=on_added,
    on_notification=on_notification,
)
client.start()
print("Listening for 30 seconds...")
time.sleep(30)
client.stop()
print("done")
