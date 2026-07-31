import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID  = int(os.environ.get("GROUP_ID"))
ADMIN_ID  = int(os.environ.get("ADMIN_ID"))

ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
]
