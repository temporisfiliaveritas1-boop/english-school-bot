import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_ID  = int(os.environ.get("GROUP_ID"))
ADMIN_ID  = int(os.environ.get("ADMIN_ID"))

ADMIN_IDS = [
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip()
]

# ID топиков в группе
SPEAKING_CLUB_THREAD_ID = int(os.environ.get("SPEAKING_CLUB_THREAD_ID", 5))
CHATTING_THREAD_ID      = int(os.environ.get("CHATTING_THREAD_ID", 3))
UPDATES_THREAD_ID       = int(os.environ.get("UPDATES_THREAD_ID", 2))
