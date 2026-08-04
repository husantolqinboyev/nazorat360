from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

router = Router()

START_TEXT = """<b>🛡️ Guruhmaster Bot</b>

Salom! Men Telegram guruhlaridagi spam va noqonuniy xabarlarni avtomatik tozalab beraman.

<b>🔍 Mening imkoniyatlarim:</b>
✅ 18+ emoji va kontentni aniqlash
✅ Spam xabarlarni avtomatik o'chirish
✅ 3 bosqichli ogohlantirish tizimi
✅ 6 soatlik TTL (vaqtinchalik ogohlantirish)
✅ Global qora ro'yxat (Blacklist)

<b>👨‍💼 Guruh egasi uchun:</b>
Botni guruhingizga admin qilib qo'shing — men avtomatik ravishda guruhni himoya qilaman!

<i>⚠️ Eslatma: Bot faqat admin huquqlari bilan ishlaydi.</i>
"""


@router.message(CommandStart())
async def cmd_start(message: Message, bot):
    bot_info = await bot.get_me()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Botni guruhga qo'shish",
            url=f"https://t.me/{bot_info.username}?startgroup=true"
        )]
    ])

    await message.answer(START_TEXT, reply_markup=kb, parse_mode="HTML")
