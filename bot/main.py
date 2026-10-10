import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from bot.config import BOT_TOKEN
from bot.database.connection import create_pool, close_pool, init_tables
from bot.database.queries import cleanup_expired_warnings
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

_polling_alive = False


async def run_bot_polling():
    global _polling_alive
    try:
        retry_delay = 5
        while True:
            try:
                await create_pool()
                await init_tables()
                logger.info("Database tayyor")
                logger.info("Bot polling boshlandi...")
                _polling_alive = True
                retry_delay = 5
                await dp.start_polling(bot)
                logger.warning("Polling to'xtadi, qayta ishga tushiriladi")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Polling/ulanish xatosi: {e}")
            finally:
                _polling_alive = False
                try:
                    await close_pool()
                except Exception:
                    pass

            logger.info(f"{retry_delay} soniyadan keyin qayta ulanish urinishi")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
    except asyncio.CancelledError:
        logger.info("Bot polling bekor qilindi")
    finally:
        _polling_alive = False
        try:
            await bot.session.close()
        except Exception:
            pass


async def cleanup_loop():
    while True:
        await asyncio.sleep(3600)
        try:
            removed = await cleanup_expired_warnings()
            if removed:
                logger.info(f"Muddati o'tgan {removed} ta warning tozalandi")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Cleanup xatosi: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    polling_task = asyncio.create_task(run_bot_polling())
    cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("Bot ishga tushdi")
    yield
    polling_task.cancel()
    cleanup_task.cancel()
    for task in (polling_task, cleanup_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health_check():
    # Render health checks must reflect the web process, not Telegram's
    # temporary connection state. Polling reconnects in the background.
    return {
        "status": "ok",
        "bot": "Guruhmaster Bot",
        "polling": _polling_alive,
        "message": "polling active" if _polling_alive else "polling reconnecting",
    }


@app.get("/")
async def root():
    return {"status": "ok", "bot": "Guruhmaster Bot"}


@app.head("/")
async def head_root():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
