import asyncpg
import logging
from bot.config import DATABASE_URL

logger = logging.getLogger(__name__)

pool: asyncpg.Pool = None


async def create_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
        logger.info("Database pool yaratildi")
    except Exception as e:
        logger.error(f"Database xatosi: {e}")
        raise


async def close_pool():
    global pool
    if pool:
        await pool.close()
        logger.info("Database pool yopildi")


async def init_tables():
    global pool
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    group_id BIGINT PRIMARY KEY,
                    group_name VARCHAR(255),
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    full_name VARCHAR(255),
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warnings_log (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    group_id BIGINT NOT NULL,
                    warn_count INTEGER DEFAULT 1,
                    action VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Database jadvallari yaratildi")
    except Exception as e:
        logger.error(f"Jadvallar yaratishda xato: {e}")
        raise


async def get_pool():
    return pool
