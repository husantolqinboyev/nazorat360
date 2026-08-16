from bot.database.connection import get_pool


async def add_group(group_id: int, group_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO groups (group_id, group_name)
            VALUES ($1, $2)
            ON CONFLICT (group_id) DO UPDATE SET group_name = $2
        """, group_id, group_name)


async def remove_group(group_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM groups WHERE group_id = $1", group_id)


async def get_all_groups():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT group_id, group_name FROM groups")
        return [dict(row) for row in rows]


async def get_groups_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM groups")
        return result


async def add_to_blacklist(user_id: int, username: str, full_name: str, reason: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO blacklist (user_id, username, full_name, reason)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                username = $2, full_name = $3, reason = $4, banned_at = CURRENT_TIMESTAMP
        """, user_id, username or "", full_name or "", reason)


async def is_blacklisted(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM blacklist WHERE user_id = $1)",
            user_id
        )
        return result


async def get_blacklist_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM blacklist")
        return result


async def get_blacklist_all():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, username, full_name, reason, banned_at FROM blacklist ORDER BY banned_at DESC"
        )
        return [dict(row) for row in rows]


async def get_blacklist_page(page: int, per_page: int = 15):
    pool = await get_pool()
    async with pool.acquire() as conn:
        offset = (page - 1) * per_page
        rows = await conn.fetch(
            "SELECT user_id, username, full_name, reason, banned_at FROM blacklist ORDER BY banned_at DESC LIMIT $1 OFFSET $2",
            per_page, offset
        )
        return [dict(row) for row in rows]


async def get_blacklist_total():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM blacklist")
        return result or 0


async def remove_from_blacklist(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM blacklist WHERE user_id = $1", user_id)


async def log_warning(user_id: int, group_id: int, warn_count: int, action: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO warnings_log (user_id, group_id, warn_count, action)
            VALUES ($1, $2, $3, $4)
        """, user_id, group_id, warn_count, action)


async def get_group_warned_count(group_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM warnings_log
            WHERE group_id = $1 AND action = 'warned'
        """, group_id)
        return result or 0


async def get_group_banned_count(group_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT COUNT(DISTINCT user_id) FROM warnings_log
            WHERE group_id = $1 AND action = 'banned'
        """, group_id)
        return result or 0


async def get_group_total_warnings(group_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("""
            SELECT COUNT(*) FROM warnings_log
            WHERE group_id = $1
        """, group_id)
        return result or 0


async def search_groups(keyword: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{keyword}%"
        )
        return [dict(row) for row in rows]


async def get_groups_with_links():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT group_id, group_name FROM groups ORDER BY added_at DESC"
        )
        return [dict(row) for row in rows]
