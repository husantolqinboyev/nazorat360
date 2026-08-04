import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

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


async def main():
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
    asyncio.run(main())
