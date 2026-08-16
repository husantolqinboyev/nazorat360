import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAnimation
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

from bot.config import ADMIN_ID
from bot.database.queries import get_all_groups, search_groups

router = Router()
logger = logging.getLogger(__name__)

broadcast_states = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_broadcast_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")]
    ])


@router.message(Command("broadcast"), F.chat.type == "private")
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    broadcast_states[message.from_user.id] = {
        "step": "waiting_content",
        "media": None,
        "text": None,
        "caption": None,
        "button_text": None,
        "button_url": None,
        "keyword": None,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Faqat matn", callback_data="bc_type_text"),
            InlineKeyboardButton(text="📎 Media + matn", callback_data="bc_type_media"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")]
    ])

    await message.answer(
        "📢 <b>E'lon Yuborish</b>\n\n"
        "E'lon turini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "bc_type_text")
async def bc_type_text(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["step"] = "waiting_text"
    state["media"] = None

    await callback.message.edit_text(
        "📝 <b>E'lon matnini yuboring:</b>\n\n"
        "HTML formatda yozishingiz mumkin:\n"
        "- <b>qalin</b>\n"
        "- <i>egri</i>\n"
        "- <code>kod</code>\n"
        "- <a href=\"url\">havola</a>",
        reply_markup=get_broadcast_cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "bc_type_media")
async def bc_type_media(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["step"] = "waiting_media"

    await callback.message.edit_text(
        "📎 <b>Media faylni yuboring:</b>\n\n"
        "Foto, video, dokument yoki GIF yuboring.\n"
        "Caption ham qo'shishingiz mumkin.",
        reply_markup=get_broadcast_cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def bc_cancel(callback: CallbackQuery):
    if callback.from_user.id in broadcast_states:
        del broadcast_states[callback.from_user.id]

    await callback.message.edit_text("❌ E'lon yuborish bekor qilindi.")
    await callback.answer()


@router.message(Command("cancel"), F.chat.type == "private")
async def cmd_cancel(message: Message):
    if message.from_user.id in broadcast_states:
        del broadcast_states[message.from_user.id]
        await message.answer("❌ E'lon yuborish bekor qilindi.")


@router.message(F.from_user.id == ADMIN_ID, F.chat.type == "private")
async def handle_broadcast_content(message: Message, bot: Bot):
    state = broadcast_states.get(message.from_user.id)
    if not state:
        return

    step = state.get("step")

    if step == "waiting_text":
        state["text"] = message.html_text
        state["step"] = "waiting_button"
        state["caption"] = message.html_text

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data="bc_button_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="bc_button_no"),
            ]
        ])

        await message.answer(
            "🔗 <b>Tugma (URL) qo'shishni xohlaysizmi?</b>\n\n"
            "Tugma bosilganda ochiladigan havolani belgilang.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if step == "waiting_media":
        media_types = ["photo", "video", "document", "animation"]
        has_media = any(getattr(message, mt, None) for mt in media_types)

        if not has_media:
            await message.answer("⚠️ Iltimos, media fayl yuboring (foto, video, dokument, GIF).")
            return

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

        state["caption"] = message.html_text or message.caption or ""
        state["media"] = True
        state["step"] = "waiting_button"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data="bc_button_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="bc_button_no"),
            ]
        ])

        await message.answer(
            "🔗 <b>Tugma (URL) qo'shishni xohlaysizmi?</b>\n\n"
            "Tugma bosilganda ochiladigan havolani belgilang.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if step == "waiting_button_text":
        state["button_text"] = message.text
        state["step"] = "waiting_button_url"

        await message.answer(
            "🔗 <b>Tugma URL havolasini yuboring:</b>\n\n"
            "Masalan: https://example.com",
            reply_markup=get_broadcast_cancel_kb(),
            parse_mode="HTML"
        )
        return

    if step == "waiting_button_url":
        url = message.text.strip()
        if not url.startswith(("http://", "https://")):
            await message.answer(
                "⚠️ Noto'g'ri URL. HTTP yoki HTTPS bilan boshlanishi kerak.\n"
                "Qaytadan yuboring yoki /cancel bekor qiling.",
                reply_markup=get_broadcast_cancel_kb()
            )
            return

        state["button_url"] = url
        state["step"] = "waiting_keyword"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Barcha guruhlarga", callback_data="bc_target_all"),
                InlineKeyboardButton(text="🔍 Kalit so'z bilan", callback_data="bc_target_keyword"),
            ]
        ])

        await message.answer(
            "🎯 <b>Qaysi guruhlarga yuborishni xohlaysiz?</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if step == "waiting_keyword":
        state["keyword"] = message.text
        await show_preview(message, state)
        return


@router.callback_query(F.data == "bc_button_yes")
async def bc_button_yes(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["step"] = "waiting_button_text"

    await callback.message.edit_text(
        "🔗 <b>Tugma matnini yozing:</b>\n\n"
        "Masalan: 🔗 Batafsil, 📲 Yuklab olish, 🌐 Saytga o'tish",
        reply_markup=get_broadcast_cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "bc_button_no")
async def bc_button_no(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["step"] = "waiting_keyword"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Barcha guruhlarga", callback_data="bc_target_all"),
            InlineKeyboardButton(text="🔍 Kalit so'z bilan", callback_data="bc_target_keyword"),
        ]
    ])

    await callback.message.edit_text(
        "🎯 <b>Qaysi guruhlarga yuborishni xohlaysiz?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "bc_target_all")
async def bc_target_all(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["keyword"] = None
    await show_preview_callback(callback, state)


@router.callback_query(F.data == "bc_target_keyword")
async def bc_target_keyword(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return

    state["step"] = "waiting_keyword"

    await callback.message.edit_text(
        "🔍 <b>Guruh nomidagi kalit so'zni yozing:</b>\n\n"
        "Masalan: IT, biznes, talabalar",
        reply_markup=get_broadcast_cancel_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


async def show_preview(message: Message, state: dict):
    groups = await get_all_groups()
    if state.get("keyword"):
        groups = await search_groups(state["keyword"])

    preview_text = state.get("caption") or state.get("text", "")

    media_info = ""
    if state.get("media"):
        media_info = f"\n📎 Media turi: {state['media_type']}"

    button_info = ""
    if state.get("button_text") and state.get("button_url"):
        button_info = f"\n🔗 Tugma: {state['button_text']} → {state['button_url']}"

    keyword_info = ""
    if state.get("keyword"):
        keyword_info = f"\n🔍 Kalit so'z: {state['keyword']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="bc_confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel"),
        ]
    ])

    await message.answer(
        f"📢 <b>E'lon preview</b>\n\n"
        f"📝 Matn: <i>{preview_text[:200]}</i>"
        f"{media_info}"
        f"{button_info}"
        f"{keyword_info}\n\n"
        f"👥 Yuboriladigan guruhlar: <b>{len(groups)}</b>\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=kb,
        parse_mode="HTML"
    )


async def show_preview_callback(callback: CallbackQuery, state: dict):
    groups = await get_all_groups()
    if state.get("keyword"):
        groups = await search_groups(state["keyword"])

    preview_text = state.get("caption") or state.get("text", "")

    media_info = ""
    if state.get("media"):
        media_info = f"\n📎 Media turi: {state['media_type']}"

    button_info = ""
    if state.get("button_text") and state.get("button_url"):
        button_info = f"\n🔗 Tugma: {state['button_text']} → {state['button_url']}"

    keyword_info = ""
    if state.get("keyword"):
        keyword_info = f"\n🔍 Kalit so'z: {state['keyword']}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="bc_confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel"),
        ]
    ])

    await callback.message.edit_text(
        f"📢 <b>E'lon preview</b>\n\n"
        f"📝 Matn: <i>{preview_text[:200]}</i>"
        f"{media_info}"
        f"{button_info}"
        f"{keyword_info}\n\n"
        f"👥 Yuboriladigan guruhlar: <b>{len(groups)}</b>\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "bc_confirm")
async def confirm_broadcast(callback: CallbackQuery, bot: Bot):
    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik yuz berdi.", show_alert=True)
        return

    await callback.message.edit_text("⏳ E'lon tarqatilmoqda...")
    await callback.answer()

    groups = await get_all_groups()
    if state.get("keyword"):
        groups = await search_groups(state["keyword"])

    success = 0
    failed = 0

    button = None
    if state.get("button_text") and state.get("button_url"):
        button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=state["button_text"], url=state["button_url"])]
        ])

    for group in groups:
        try:
            if state.get("media"):
                if state["media_type"] == "photo":
                    await bot.send_photo(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        reply_markup=button,
                        parse_mode=ParseMode.HTML
                    )
                elif state["media_type"] == "video":
                    await bot.send_video(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        reply_markup=button,
                        parse_mode=ParseMode.HTML
                    )
                elif state["media_type"] == "document":
                    await bot.send_document(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        reply_markup=button,
                        parse_mode=ParseMode.HTML
                    )
                elif state["media_type"] == "animation":
                    await bot.send_animation(
                        group["group_id"],
                        state["file_id"],
                        caption=state.get("caption", ""),
                        reply_markup=button,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await bot.send_message(
                    group["group_id"],
                    state.get("text", ""),
                    reply_markup=button,
                    parse_mode=ParseMode.HTML
                )
            success += 1
            await asyncio.sleep(0.5)

        except Exception as e:
            failed += 1
            logger.error(f"Guruh {group['group_id']} ga yuborishda xato: {e}")

    del broadcast_states[callback.from_user.id]

    await callback.message.edit_text(
        f"✅ <b>E'lon tarqatildi!</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>\n"
        f"👥 Jami guruhlar: <b>{len(groups)}</b>"
    )
