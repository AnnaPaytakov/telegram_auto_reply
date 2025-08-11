import os
import asyncio
from datetime import datetime, timedelta, time
from telethon import TelegramClient, events, functions
from telethon.tl.types import PeerUser
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
SESSION = os.getenv("SESSION", "tg_autoreply.session")

AUTO_REPLY_TEXT = os.getenv("AUTO_REPLY_TEXT")

#* MODE=always — отвечаем всегда
#* MODE=schedule — отвечаем только ВНЕ рабочего времени
MODE = os.getenv("MODE")


WORK_START = os.getenv("WORK_START", "10:00")
WORK_END = os.getenv("WORK_END", "19:00")

REPLY_COOLDOWN_HOURS = int(os.getenv("REPLY_COOLDOWN_HOURS", "1"))

IGNORE_USERS = set(u.strip() for u in os.getenv("IGNORE_USERS", "").split(",") if u.strip())

DND_ENABLED = os.getenv("DND_DEFAULT", "off").lower() == "on"

last_replied_at = {}

def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))

WORK_START_T = parse_hhmm(WORK_START)
WORK_END_T = parse_hhmm(WORK_END)

def is_work_time(now: datetime) -> bool:
    start = datetime.combine(now.date(), WORK_START_T)
    end = datetime.combine(now.date(), WORK_END_T)
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end

def should_autoreply(now: datetime) -> bool:
    if DND_ENABLED:
        return True
    if MODE == "always":
        return True
    if MODE == "schedule":
        return not is_work_time(now)
    return True

client = TelegramClient(SESSION, API_ID, API_HASH)

@client.on(events.NewMessage(incoming=True))
async def handler(event: events.NewMessage.Event):
    if not isinstance(event.peer_id, PeerUser):
        return

    sender = await event.get_sender()
    if sender.is_self or getattr(sender, "bot", False):
        return

    if str(sender.id) in IGNORE_USERS or (sender.username and sender.username.lower() in IGNORE_USERS):
        return

    now = datetime.now()
    if not should_autoreply(now):
        return

    last = last_replied_at.get(sender.id)
    if last and now - last < timedelta(hours=REPLY_COOLDOWN_HOURS):
        return

    try:
        await event.reply(AUTO_REPLY_TEXT)
        last_replied_at[sender.id] = now
    except Exception as e:
        print("Send failed:", e)

@client.on(events.NewMessage(outgoing=True, pattern=r"^/dnd\s+(on|off)$"))
async def dnd_toggle(event: events.NewMessage.Event):
    global DND_ENABLED
    arg = event.pattern_match.group(1)
    DND_ENABLED = (arg == "on")
    await event.reply(f"DND: {'ON' if DND_ENABLED else 'OFF'}")

async def main():
    try:
        await client(functions.account.UpdateStatusRequest(offline=True))
    except Exception:
        pass

    print("Auto-reply is running. Mode:", MODE)
    await client.run_until_disconnected()

if __name__ == "__main__":
    async def runner():
        await client.start(phone=PHONE if PHONE else None)
        await main()
    asyncio.run(runner())
