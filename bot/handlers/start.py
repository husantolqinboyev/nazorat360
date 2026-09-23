from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from bot.database.queries import save_user

router = Router()

START_TEXT = """<b>🛡️ Guruhmaster Bot</b>

Salom! Men Telegram guruhlaridagi spam va noqonuniy xabarlarni avtomatik tozalab beraman.

<b>🔍 Mening imkoniyatlarim:</b>
✅ 18+ emoji va kontentni aniqlash
✅ Spam xabarlarni avtomatik o'chirish
✅ APK fayllarni avtomatik tozalash
✅ 3 bosqichli ogohlantirish tizimi
✅ 6 soatlik TTL (vaqtinchalik ogohlantirish)
✅ Global qora ro'yxat (Blacklist)

<b>👨‍💼 Guruh egasi uchun:</b>
Botni guruhingizga admin qilib qo'shing — men avtomatik ravishda guruhni himoya qilaman!

<i>⚠️ Eslatma: Bot faqat admin huquqlari bilan ishlaydi.</i>
"""


@router.message(CommandStart())
async def cmd_start(message: Message, bot):
    user = message.from_user
    if user:
        try:
            await save_user(user.id, user.username, user.full_name)
        except Exception:
            pass

    bot_info = await bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Botni guruhga qo'shish",
            url=f"https://t.me/{bot_info.username}?startgroup=true"
        )]
    ])

    await message.answer(START_TEXT, reply_markup=kb)
