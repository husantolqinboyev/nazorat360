import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from bot.config import ADMIN_ID
from bot.database.queries import (
    get_groups_count, get_blacklist_count,
    get_blacklist_all, remove_from_blacklist,
    get_groups_with_links
)

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_main_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Dashboard", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Guruhlar", callback_data="admin_groups"),
        ],
        [
            InlineKeyboardButton(text="🚫 Qora ro'yxat", callback_data="admin_blacklist"),
            InlineKeyboardButton(text="📢 E'lon yuborish", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Yordam", callback_data="admin_help"),
        ],
    ])


@router.message(Command("panel"), F.chat.type == "private")
async def cmd_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    await message.answer(
        "🛡️ <b>Guruhmaster Bot — Admin Panel</b>\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )


@router.message(Command("admin"), F.chat.type == "private")
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    await message.answer(
        "🛡️ <b>Guruhmaster Bot — Admin Panel</b>\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    groups_count = await get_groups_count()
    blacklist_count = await get_blacklist_count()

    await callback.message.edit_text(
        f"📊 <b>Dashboard</b>\n\n"
        f"👥 Guruhlar soni: <b>{groups_count}</b>\n"
        f"🚫 Qora ro'yxat: <b>{blacklist_count}</b> foydalanuvchi\n\n"
        f"<i>Real vaqt rejimida yangilanadi.</i>",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_groups")
async def admin_groups(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    groups = await get_groups_with_links()

    if not groups:
        await callback.message.edit_text(
            "👥 <b>Guruhlar ro'yxati</b>\n\n"
            "Hozircha hech qanday guruh yo'q.\n"
            "Botni guruhga qo'shing — avtomatik ro'yxatga olinadi.",
            reply_markup=get_main_panel(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = f"👥 <b>Guruhlar ro'yxati ({len(groups)} ta):</b>\n\n"

    for i, group in enumerate(groups[:20], 1):
        name = group['group_name'] or "Noma'lum"
        gid = group['group_id']
        link = f"https://t.me/c/{str(gid).replace('-100', '')}"
        text += f"{i}. <b>{name}</b>\n"
        text += f"   🆔 <code>{gid}</code>\n"
        text += f"   🔗 <a href=\"{link}\">Havola</a>\n\n"

    if len(groups) > 20:
        text += f"<i>...va yana {len(groups) - 20} ta guruh.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_blacklist")
async def admin_blacklist(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    users = await get_blacklist_all()

    if not users:
        await callback.message.edit_text(
            "🚫 <b>Qora ro'yxat</b>\n\n"
            "Qora ro'yxat bo'sh.",
            reply_markup=get_main_panel(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = f"🚫 <b>Global Qora Ro'yxat ({len(users)} ta):</b>\n\n"

    for i, user in enumerate(users[:15], 1):
        name = user['full_name'] or "Noma'lum"
        uname = f"@{user['username']}" if user['username'] else "username yo'q"
        reason = user['reason'] or " sabab ko'rsatilmagan"
        text += f"{i}. <b>{name}</b> ({uname})\n"
        text += f"   🆔 <code>{user['user_id']}</code>\n"
        text += f"   📋 Sabab: {reason}\n\n"

    if len(users) > 15:
        text += f"<i>...va yana {len(users) - 15} ta foydalanuvchi.</i>"

    text += "\n\n<i>Ban bekor qilish: /unban USER_ID</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
    ])

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        "📢 <b>E'lon Yuborish</b>\n\n"
        "E'lon yuborish uchun /broadcast buyrug'ini ishlating.\n\n"
        "<b>Imkoniyatlar:</b>\n"
        "✅ Matn e'lon\n"
        "✅ Foto + matn\n"
        "✅ Video + matn\n"
        "✅ Fayl + matn\n"
        "✅ Tugma (URL havola) qo'shish\n"
        "✅ Kalit so'z bo'yicha guruhlarni tanlash",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_help")
async def admin_help(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        "ℹ️ <b>Yordam</b>\n\n"
        "<b>Buyruqlar:</b>\n"
        "/panel — Admin panelni ochish\n"
        "/stats — Dashboard statistikasi\n"
        "/broadcast — E'lon yuborish\n"
        "/blacklist — Qora ro'yxat\n"
        "/unban USER_ID — Ban bekor qilish\n"
        "/status GURUH_ID — Guruh holati\n"
        "/help — Yordam\n\n"
        "<b>E'lon yuborish qadamlari:</b>\n"
        "1️⃣ /broadcast buyrug'ini yuboring\n"
        "2️⃣ Media fayl yoki matn yuboring\n"
        "3️⃣ Tugma (URL) qo'shing (ixtiyoriy)\n"
        "4️⃣ Tasdiqlang\n\n"
        "<i>Barcha buyruqlar faqat shaxsiy chatda ishlaydi.</i>",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        "🛡️ <b>Guruhmaster Bot — Admin Panel</b>\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("stats"), F.chat.type == "private")
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    groups_count = await get_groups_count()
    blacklist_count = await get_blacklist_count()

    await message.answer(
        f"📊 <b>Dashboard</b>\n\n"
        f"👥 Guruhlar soni: <b>{groups_count}</b>\n"
        f"🚫 Qora ro'yxat: <b>{blacklist_count}</b> foydalanuvchi",
        reply_markup=get_main_panel(),
        parse_mode="HTML"
    )


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
        reply_markup=get_main_panel(),
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
        "/panel — Admin panelni ochish\n"
        "/stats — Dashboard statistikasi\n"
        "/broadcast — E'lon yuborish\n"
        "/blacklist — Qora ro'yxat\n"
        "/unban USER_ID — Ban bekor qilish\n"
        "/help — Yordam\n\n"
        "<i>Barcha buyruqlar faqat shaxsiy chatda ishlaydi.</i>",
        reply_markup=get_main_panel(),
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
