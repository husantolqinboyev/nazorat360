import asyncio
import logging
import threading
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from fastapi import FastAPI
import uvicorn

from bot.config import BOT_TOKEN
from bot.database.connection import create_pool, close_pool, init_tables
from bot.handlers import start, group, admin, broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

dp.include_routers(
    start.router,
    group.router,
    admin.router,
    broadcast.router
)

app = FastAPI()


@app.get("/health")
async def health_check():
    return {"status": "ok", "bot": "Guruhmaster Bot"}


@app.get("/")
async def root():
    return {"status": "ok", "bot": "Guruhmaster Bot", "message": "Bot ishlayapti!"}


def run_fastapi():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


async def run_bot():
    try:
        await create_pool()
        await init_tables()
        logger.info("Database tayyor")
        logger.info("Bot polling boshlandi...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot xatosi: {e}")
    finally:
        await close_pool()
        await bot.session.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()
    logger.info("FastAPI server ishga tushdi (port 8000)")

    asyncio.run(run_bot())
