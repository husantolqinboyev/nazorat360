import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command

from bot.config import ADMIN_ID
from bot.database.queries import get_all_groups

router = Router()
logger = logging.getLogger(__name__)

broadcast_state = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    broadcast_state[message.from_user.id] = {"step": "waiting_text"}

    await message.answer(
        "📢 <b>E'lon Yuborish Rejimi</b>\n\n"
        "Endi e'lon matnini yoki media faylni yuboring.\n"
        "Qo'shimcha matn ham qo'shishingiz mumkin.\n\n"
        "<i>Bekor qilish: /cancel</i>",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    if message.from_user.id in broadcast_state:
        del broadcast_state[message.from_user.id]
        await message.answer("❌ E'lon yuborish bekor qilindi.")
        return


@router.message(F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def handle_broadcast_content(message: Message, bot: Bot):
    state = broadcast_state.get(message.from_user.id)
    if not state or state.get("step") != "waiting_text":
        return

    media_types = ["photo", "video", "document", "animation"]
    has_media = any(getattr(message, mt, None) for mt in media_types)

    if has_media:
        state["media"] = True
        state["message_id"] = message.message_id
        state["chat_id"] = message.chat.id

        if message.photo:
            state["media_type"] = "photo"
            state["file_id"] = message.photo[-1].file_id
        elif message.video:
            state["media_type"] = "video"
            state["file_id"] = message.video.file_id
        elif message.document:
            state["media_type"] = "document"
            state["file_id"] = message.document.file_id
        elif message.animation:
            state["media_type"] = "animation"
            state["file_id"] = message.animation.file_id

        state["caption"] = message.caption or ""

    else:
        state["media"] = False
        state["text"] = message.text

    state["step"] = "confirming"

    groups_count = await get_all_groups()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast_cancel")
        ]
    ])

    media_info = ""
    if has_media:
        media_info = f"\n📎 Media turi: {state['media_type']}"

    await message.answer(
        f"📢 <b>E'lon tasdig'i</b>\n\n"
        f"📋 Xabar turi: {'Media + Matn' if has_media else 'Faqat matn'}"
        f"{media_info}\n\n"
        f"📝 Matn: <i>{state.get('caption', state.get('text', ''))[:200]}</i>\n\n"
        f"👥 Yuboriladigan guruhlar: <b>{len(groups_count)}</b>\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "broadcast_confirm")
async def confirm_broadcast(callback: CallbackQuery, bot: Bot):
    state = broadcast_state.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik yuz berdi.")
        return

    await callback.message.edit_text("⏳ E'lon tarqatilmoqda...")
    await callback.answer()

    groups = await get_all_groups()
    success = 0
    failed = 0

    for group in groups:
        try:
            if state.get("media"):
                if state["media_type"] == "photo":
                    await bot.send_photo(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        parse_mode="HTML"
                    )
                elif state["media_type"] == "video":
                    await bot.send_video(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        parse_mode="HTML"
                    )
                elif state["media_type"] == "document":
                    await bot.send_document(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        parse_mode="HTML"
                    )
                elif state["media_type"] == "animation":
                    await bot.send_animation(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        parse_mode="HTML"
                    )
            else:
                await bot.send_message(
                    group["group_id"],
                    state["text"],
                    parse_mode="HTML"
                )
            success += 1
            await asyncio.sleep(0.5)

        except Exception as e:
            failed += 1
            logger.error(f"Guruh {group['group_id']} ga yuborishda xato: {e}")

    del broadcast_state[callback.from_user.id]

    await callback.message.edit_text(
        f"✅ <b>E'lon tarqatildi!</b>\n\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xatolik: {failed}\n"
        f"👥 Jami guruhlar: {len(groups)}"
    )


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery):
    if callback.from_user.id in broadcast_state:
        del broadcast_state[callback.from_user.id]

    await callback.message.edit_text("❌ E'lon yuborish bekor qilindi.")
    await callback.answer()
