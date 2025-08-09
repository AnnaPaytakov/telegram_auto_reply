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

# Режимы работы:
# MODE=always — отвечаем всегда (пока включён скрипт)
# MODE=schedule — отвечаем только ВНЕ рабочего времени (см. ниже)
MODE = os.getenv("MODE", "schedule")

# Рабочие часы, когда НЕ надо отвечать (для MODE=schedule)
WORK_START = os.getenv("WORK_START", "10:00")
WORK_END = os.getenv("WORK_END", "19:00")

# Кулдаун на одного пользователя (чтобы не спамить): часы
REPLY_COOLDOWN_HOURS = int(os.getenv("REPLY_COOLDOWN_HOURS", "12"))

# Список user_id или @username, кому НЕ отвечать
IGNORE_USERS = set(u.strip() for u in os.getenv("IGNORE_USERS", "").split(",") if u.strip())

# Флаг «не беспокоить» можно переключать командой с твоего аккаунта: /dnd on|off
DND_ENABLED = os.getenv("DND_DEFAULT", "off").lower() == "on"

# Хранилище времени последнего автоответа по собеседникам (в памяти)
last_replied_at = {}

def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))

WORK_START_T = parse_hhmm(WORK_START)
WORK_END_T = parse_hhmm(WORK_END)

def is_work_time(now: datetime) -> bool:
    start = datetime.combine(now.date(), WORK_START_T)
    end = datetime.combine(now.date(), WORK_END_T)
    # если интервал не «переламывает» сутки
    if start <= end:
        return start <= now <= end
    # если, например, 22:00–06:00
    return now >= start or now <= end

def should_autoreply(now: datetime) -> bool:
    if DND_ENABLED:
        return True
    if MODE == "always":
        return True
    if MODE == "schedule":
        # автоответ ТОЛЬКО вне рабочего времени
        return not is_work_time(now)
    return True

client = TelegramClient(SESSION, API_ID, API_HASH)

@client.on(events.NewMessage(incoming=True))
async def handler(event: events.NewMessage.Event):
    # Только личные чаты (не каналы/группы)
    if not isinstance(event.peer_id, PeerUser):
        return

    sender = await event.get_sender()
    if sender.is_self or getattr(sender, "bot", False):
        return

    # Игнор-лист (по id или username)
    if str(sender.id) in IGNORE_USERS or (sender.username and sender.username.lower() in IGNORE_USERS):
        return

    now = datetime.now()
    if not should_autoreply(now):
        return

    # Антиспам: отвечаем пользователю не чаще, чем раз в N часов
    last = last_replied_at.get(sender.id)
    if last and now - last < timedelta(hours=REPLY_COOLDOWN_HOURS):
        return

    # Отправляем ответ
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
    # Хитрость: помечаем аккаунт «офлайн», чтобы не светиться онлайн (по желанию)
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
