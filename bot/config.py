import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi — .env faylini tekshiring")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL topilmadi — .env faylini tekshiring")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID noto'g'ri — Telegram ID raqamingizni kiriting")
