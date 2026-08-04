import asyncio
import logging
from contextlib import asynccontextmanager

import aiohttp
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


async def self_ping():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/health") as resp:
                    logger.info(f"Self-ping: {resp.status}")
        except Exception as e:
            logger.warning(f"Self-ping xatosi: {e}")
        await asyncio.sleep(240)


async def run_bot_polling():
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    polling_task = asyncio.create_task(run_bot_polling())
    ping_task = asyncio.create_task(self_ping())
    logger.info("Bot va keep-alive ishga tushdi")
    yield
    polling_task.cancel()
    ping_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass
    try:
        await ping_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok", "bot": "Guruhmaster Bot"}


@app.get("/")
async def root():
    return {"status": "ok", "bot": "Guruhmaster Bot"}


@app.head("/")
async def head_root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
