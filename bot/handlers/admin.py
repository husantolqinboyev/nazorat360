from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from bot.config import ADMIN_ID
from bot.database.queries import (
    get_groups_count, get_blacklist_count,
    get_blacklist_all, remove_from_blacklist
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@router.message(Command("stats"), F.chat.type == "private")
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    groups_count = await get_groups_count()
    blacklist_count = await get_blacklist_count()

    await message.answer(
        f"📊 <b>Guruhmaster Bot Dashboard</b>\n\n"
        f"👥 Guruhlar soni: <b>{groups_count}</b>\n"
        f"🚫 Qora ro'yxat: <b>{blacklist_count}</b> foydalanuvchi\n\n"
        f"<i>Real vaqt rejimida yangilanadi.</i>",
        parse_mode="HTML"
    )


@router.message(Command("blacklist"), F.chat.type == "private")
async def cmd_blacklist(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    users = await get_blacklist_all()

    if not users:
        await message.answer("📋 Qora ro'yxat bo'sh.")
        return

    text = "🚫 <b>Global Qora Ro'yxat:</b>\n\n"
    for i, user in enumerate(users[:20], 1):
        name = user['full_name'] or "Noma'lum"
        uname = f"@{user['username']}" if user['username'] else "username yo'q"
        text += f"{i}. {name} ({uname}) — ID: <code>{user['user_id']}</code>\n"

    if len(users) > 20:
        text += f"\n<i>...va yana {len(users) - 20} ta foydalanuvchi.</i>"

    text += "\n\n<i>Ban bekor qilish: /unban USER_ID</i>"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("unban"), F.chat.type == "private")
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("📝 Ishlatish: /unban USER_ID")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri ID format.")
        return

    await remove_from_blacklist(user_id)
    await message.answer(
        f"✅ Foydalanuvchi <code>{user_id}</code> qora ro'yxatdan o'chirildi.",
        parse_mode="HTML"
    )


@router.message(Command("help"), F.chat.type == "private")
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    await message.answer(
        "🛡️ <b>Guruhmaster Bot — Admin Panel</b>\n\n"
        "<b>Buyruqlar:</b>\n"
        "/stats — Dashboard statistikasi\n"
        "/blacklist — Qora ro'yxat\n"
        "/unban USER_ID — Ban bekor qilish\n"
        "/broadcast — E'lon yuborish\n"
        "/help — Yordam\n\n"
        "<i>Barcha buyruqlar faqat shaxsiy chatda ishlaydi.</i>",
        parse_mode="HTML"
    )
