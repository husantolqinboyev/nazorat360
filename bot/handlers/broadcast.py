import asyncio
import logging
import re
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramForbiddenError

from bot.config import ADMIN_ID
from bot.database.queries import get_all_groups, search_groups, get_all_users, add_broadcast_log
from bot.handlers.admin import safe_edit

router = Router()
logger = logging.getLogger(__name__)

broadcast_states = {}

MEDIA_TYPES = ("photo", "video", "document", "animation")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_broadcast_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")]
    ])


def get_target_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Barcha guruhlarga", callback_data="bc_target_groups")],
        [InlineKeyboardButton(text="👤 Barcha userlarga", callback_data="bc_target_users")],
        [InlineKeyboardButton(text="👥 + 👤 Ikkalasiga", callback_data="bc_target_both")],
        [InlineKeyboardButton(text="🔍 Kalit so'z bilan (guruhlar)", callback_data="bc_target_keyword")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")],
    ])


async def _require_state(callback: CallbackQuery) -> dict | None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return None
    state = broadcast_states.get(callback.from_user.id)
    if not state:
        await callback.answer("❌ Xatolik.", show_alert=True)
        return None
    return state


@router.message(Command("broadcast"), F.chat.type == "private")
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruqni ishlatish huquqi yo'q.")
        return

    broadcast_states[message.from_user.id] = {
        "step": "waiting_type",
        "media": False,
        "media_type": None,
        "file_id": None,
        "text": None,
        "caption": None,
        "button_text": None,
        "button_url": None,
        "keyword": None,
        "target": None,
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Faqat matn", callback_data="bc_type_text"),
            InlineKeyboardButton(text="📎 Fayl + caption", callback_data="bc_type_media"),
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel")]
    ])

    await message.answer(
        "📢 <b>E'lon Yuborish</b>\n\n"
        "E'lon turini tanlang:",
        reply_markup=kb
    )


@router.callback_query(F.data == "bc_type_text")
async def bc_type_text(callback: CallbackQuery):
    state = await _require_state(callback)
    if not state:
        return

    state["step"] = "waiting_text"
    state["media"] = False
    state["media_type"] = None
    state["file_id"] = None

    await safe_edit(
        callback.message,
        "📝 <b>E'lon matnini yuboring:</b>\n\n"
        "HTML formatda yozishingiz mumkin:\n"
        "- <b>qalin</b>\n"
        "- <i>egri</i>\n"
        "- <code>kod</code>\n"
        "- <a href=\"url\">havola</a>",
        reply_markup=get_broadcast_cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_type_media")
async def bc_type_media(callback: CallbackQuery):
    state = await _require_state(callback)
    if not state:
        return

    state["step"] = "waiting_media"

    await safe_edit(
        callback.message,
        "📎 <b>Faylni yuboring:</b>\n\n"
        "Foto, video, dokument yoki GIF yuboring.\n"
        "Caption (izoh) ham qo'shishingiz mumkin.",
        reply_markup=get_broadcast_cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def bc_cancel(callback: CallbackQuery):
    if callback.from_user.id in broadcast_states:
        del broadcast_states[callback.from_user.id]

    try:
        await safe_edit(callback.message, "❌ E'lon yuborish bekor qilindi.")
    except Exception:
        pass
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
        state["caption"] = message.html_text
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
            reply_markup=kb
        )
        return

    if step == "waiting_media":
        has_media = any(getattr(message, mt, None) for mt in MEDIA_TYPES)

        if not has_media:
            await message.answer(
                "⚠️ Iltimos, fayl yuboring (foto, video, dokument, GIF)."
            )
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
        state["text"] = state["caption"]
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
            reply_markup=kb
        )
        return

    if step == "waiting_button_text":
        if not message.text:
            await message.answer("⚠️ Iltimos, oddiy matn yuboring.")
            return
        state["button_text"] = message.text[:64]
        state["step"] = "waiting_button_url"

        await message.answer(
            "🔗 <b>Tugma URL havolasini yuboring:</b>\n\n"
            "Masalan: https://example.com",
            reply_markup=get_broadcast_cancel_kb()
        )
        return

    if step == "waiting_button_url":
        url = (message.text or "").strip()
        if not url.startswith(("http://", "https://")):
            await message.answer(
                "⚠️ Noto'g'ri URL. HTTP yoki HTTPS bilan boshlanishi kerak.\n"
                "Qaytadan yuboring yoki /cancel bekor qiling.",
                reply_markup=get_broadcast_cancel_kb()
            )
            return

        state["button_url"] = url
        state["step"] = "waiting_target"
        await message.answer(
            "🎯 <b>Qaysi maqsadga yuborishni xohlaysiz?</b>",
            reply_markup=get_target_kb()
        )
        return

    if step == "waiting_keyword":
        state["keyword"] = message.text or ""
        state["target"] = "keyword"
        await show_preview(message, state)
        return


@router.callback_query(F.data == "bc_button_yes")
async def bc_button_yes(callback: CallbackQuery):
    state = await _require_state(callback)
    if not state:
        return

    state["step"] = "waiting_button_text"

    await safe_edit(
        callback.message,
        "🔗 <b>Tugma matnini yozing:</b>\n\n"
        "Masalan: 🔗 Batafsil, 📲 Yuklab olish, 🌐 Saytga o'tish",
        reply_markup=get_broadcast_cancel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "bc_button_no")
async def bc_button_no(callback: CallbackQuery):
    state = await _require_state(callback)
    if not state:
        return

    state["step"] = "waiting_target"

    await safe_edit(
        callback.message,
        "🎯 <b>Qaysi maqsadga yuborishni xohlaysiz?</b>",
        reply_markup=get_target_kb()
    )
    await callback.answer()


async def _set_target(callback: CallbackQuery, target: str) -> dict | None:
    state = await _require_state(callback)
    if not state:
        return None
    state["target"] = target
    state["keyword"] = None
    return state


@router.callback_query(F.data == "bc_target_groups")
async def bc_target_groups(callback: CallbackQuery):
    state = await _set_target(callback, "groups")
    if not state:
        return
    await show_preview_callback(callback, state)


@router.callback_query(F.data == "bc_target_users")
async def bc_target_users(callback: CallbackQuery):
    state = await _set_target(callback, "users")
    if not state:
        return
    await show_preview_callback(callback, state)


@router.callback_query(F.data == "bc_target_both")
async def bc_target_both(callback: CallbackQuery):
    state = await _set_target(callback, "both")
    if not state:
        return
    await show_preview_callback(callback, state)


@router.callback_query(F.data == "bc_target_keyword")
async def bc_target_keyword(callback: CallbackQuery):
    state = await _require_state(callback)
    if not state:
        return

    state["step"] = "waiting_keyword"
    state["target"] = "keyword"

    await safe_edit(
        callback.message,
        "🔍 <b>Guruh nomidagi kalit so'zni yozing:</b>\n\n"
        "Masalan: IT, biznes, talabalar",
        reply_markup=get_broadcast_cancel_kb()
    )
    await callback.answer()


async def _resolve_targets(state: dict) -> tuple[list, list]:
    target = state.get("target")
    groups: list = []
    users: list = []

    if target == "groups":
        groups = await get_all_groups()
    elif target == "users":
        users = await get_all_users()
    elif target == "both":
        groups = await get_all_groups()
        users = await get_all_users()
    elif target == "keyword":
        keyword = state.get("keyword") or ""
        groups = await search_groups(keyword) if keyword else []

    return groups, users


def _build_preview_text(state: dict, groups: list, users: list) -> str:
    preview_raw = state.get("caption") or state.get("text") or ""
    plain = re.sub(r"<[^>]+>", "", preview_raw)
    preview_text = escape(plain[:200])

    media_info = ""
    if state.get("media"):
        media_info = f"\n📎 Media turi: {escape(state.get('media_type') or '')}"

    button_info = ""
    if state.get("button_text") and state.get("button_url"):
        button_info = (
            f"\n🔗 Tugma: {escape(state['button_text'])} → {escape(state['button_url'])}"
        )

    keyword_info = ""
    if state.get("keyword"):
        keyword_info = f"\n🔍 Kalit so'z: {escape(state['keyword'])}"

    return (
        f"📢 <b>E'lon preview</b>\n\n"
        f"📝 Matn: <i>{preview_text}</i>"
        f"{media_info}"
        f"{button_info}"
        f"{keyword_info}\n\n"
        f"👥 Guruhlar: <b>{len(groups)}</b>\n"
        f"👤 Userlar: <b>{len(users)}</b>\n\n"
        f"Tasdiqlaysizmi?"
    )


def _get_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="bc_confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bc_cancel"),
        ]
    ])


async def show_preview(message: Message, state: dict):
    groups, users = await _resolve_targets(state)
    await message.answer(
        _build_preview_text(state, groups, users),
        reply_markup=_get_preview_kb()
    )


async def show_preview_callback(callback: CallbackQuery, state: dict):
    groups, users = await _resolve_targets(state)
    await safe_edit(
        callback.message,
        _build_preview_text(state, groups, users),
        reply_markup=_get_preview_kb()
    )
    await callback.answer()


async def _send_to(bot: Bot, chat_id: int, state: dict, button):
    if state.get("media"):
        kwargs = dict(reply_markup=button, parse_mode=ParseMode.HTML)
        caption = state.get("caption", "")
        mt = state.get("media_type")
        file_id = state["file_id"]
        if mt == "photo":
            await bot.send_photo(chat_id, file_id, caption=caption, **kwargs)
        elif mt == "video":
            await bot.send_video(chat_id, file_id, caption=caption, **kwargs)
        elif mt == "document":
            await bot.send_document(chat_id, file_id, caption=caption, **kwargs)
        elif mt == "animation":
            await bot.send_animation(chat_id, file_id, caption=caption, **kwargs)
    else:
        await bot.send_message(
            chat_id,
            state.get("text", ""),
            reply_markup=button,
            parse_mode=ParseMode.HTML
        )


async def _send_with_retry(bot: Bot, chat_id: int, state: dict, button) -> bool:
    for attempt in range(3):
        try:
            await _send_to(bot, chat_id, state, button)
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"Flood wait {e.retry_after}s — chat={chat_id}")
            await asyncio.sleep(e.retry_after + 1)
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.error(f"Chat {chat_id} ga yuborib bo'lmadi: {e}")
            return False
        except Exception as e:
            logger.error(f"Chat {chat_id} ga xato: {e}")
            return False
    return False


@router.callback_query(F.data == "bc_confirm")
async def confirm_broadcast(callback: CallbackQuery, bot: Bot):
    state = await _require_state(callback)
    if not state:
        return

    try:
        await safe_edit(callback.message, "⏳ E'lon tarqatilmoqda...")
    except Exception:
        pass
    await callback.answer()

    groups, users = await _resolve_targets(state)

    button = None
    if state.get("button_text") and state.get("button_url"):
        button = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=state["button_text"], url=state["button_url"])]
        ])

    success = 0
    failed = 0
    total = len(groups) + len(users)
    done = 0

    for group in groups:
        ok = await _send_with_retry(bot, group["group_id"], state, button)
        success += 1 if ok else 0
        failed += 0 if ok else 1
        done += 1
        await asyncio.sleep(0.5)
        if done % 20 == 0:
            try:
                await callback.message.edit_text(
                    f"⏳ E'lon tarqatilmoqda... {done}/{total}"
                )
            except Exception:
                pass

    for user in users:
        ok = await _send_with_retry(bot, user["user_id"], state, button)
        success += 1 if ok else 0
        failed += 0 if ok else 1
        done += 1
        await asyncio.sleep(0.5)
        if done % 20 == 0:
            try:
                await callback.message.edit_text(
                    f"⏳ E'lon tarqatilmoqda... {done}/{total}"
                )
            except Exception:
                pass

    broadcast_states.pop(callback.from_user.id, None)

    try:
        await add_broadcast_log(
            admin_id=callback.from_user.id,
            content_type="media" if state.get("media") else "text",
            target=state.get("target") or "unknown",
            caption=state.get("caption") or state.get("text") or "",
            button_text=state.get("button_text"),
            button_url=state.get("button_url"),
            success_count=success,
            failed_count=failed,
            total_count=total,
        )
    except Exception as e:
        logger.error(f"E'lon tarixini saqlashda xato: {e}")

    await safe_edit(
        callback.message,
        f"✅ <b>E'lon tarqatildi!</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>\n"
        f"👥 Guruhlar: <b>{len(groups)}</b>\n"
        f"👤 Userlar: <b>{len(users)}</b>\n"
        f"📨 Jami: <b>{total}</b>"
    )
