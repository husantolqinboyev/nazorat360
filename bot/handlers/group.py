import logging
import asyncio
import time
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, Command

from bot.database.queries import (
    add_group, remove_group, is_blacklisted,
    log_warning, add_to_blacklist, add_warning, reset_warnings,
    get_group_warned_count, get_group_banned_count, get_group_total_warnings,
)
from bot.utils.anti_spam import is_spam
from bot.config import ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

MAX_WARNINGS = 3

_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}
_admin_cache_ttl = 60

_notify_cooldown: dict[tuple[int, int], float] = {}
_notify_cooldown_sec = 30

_background_tasks: set = set()


def _track_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def is_user_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    if cached and time.time() - cached[1] < _admin_cache_ttl:
        return cached[0]
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in ("creator", "administrator")
    except Exception:
        result = False
    _admin_cache[key] = (result, time.time())
    return result


async def get_group_admin_ids(bot: Bot, chat_id: int) -> list[int]:
    admin_ids = []
    try:
        admins = await bot.get_chat_administrators(chat_id)
        for admin in admins:
            if admin.status == "creator":
                admin_ids.insert(0, admin.user.id)
            elif admin.status == "administrator":
                admin_ids.append(admin.user.id)
    except Exception as e:
        logger.error(f"Guruh adminlarini olishda xato: {e}")
    return admin_ids


async def notify_group_admins(
    bot: Bot, chat_id: int, chat_title: str, text: str,
    exclude_user_id: int = None, force: bool = False
):
    key = (chat_id, 0)
    now = time.time()
    if not force and now - _notify_cooldown.get(key, 0) < _notify_cooldown_sec:
        return
    _notify_cooldown[key] = now

    admin_ids = await get_group_admin_ids(bot, chat_id)
    safe_title = escape(chat_title or "Noma'lum guruh")
    for admin_id in admin_ids:
        if admin_id == exclude_user_id:
            continue
        try:
            await bot.send_message(
                admin_id,
                f"🛡️ <b>Guruhmaster hisobot</b>\n"
                f"📍 Guruh: <b>{safe_title}</b>\n\n"
                f"{text}"
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")


def _is_apk(message: Message) -> bool:
    doc = message.document
    if not doc:
        return False
    name = (doc.file_name or "").lower()
    mime = (doc.mime_type or "").lower()
    return name.endswith(".apk") or mime == "application/vnd.android.package-archive"


@router.chat_member(ChatMemberUpdatedFilter(
    member_status_changed=IS_NOT_MEMBER >> IS_MEMBER
))
async def on_bot_added(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in ("group", "supergroup"):
        await add_group(chat.id, chat.title)
        logger.info(f"Bot guruhga qo'shildi: {chat.title} ({chat.id})")

        await event.answer(
            "🛡️ <b>Guruhmaster Bot</b> muvaffaqiyatli qo'shildi!\n\n"
            "Men bu guruhdagi spam va noqonuniy xabarlarni avtomatik tozalayman.\n"
            "<i>Admin huquqlari talab qilinadi.</i>"
        )


@router.chat_member(ChatMemberUpdatedFilter(
    member_status_changed=IS_MEMBER >> IS_NOT_MEMBER
))
async def on_bot_removed(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in ("group", "supergroup"):
        await remove_group(chat.id)
        logger.info(f"Bot guruhdan chiqarildi: {chat.title} ({chat.id})")


@router.message(Command("status"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_status(message: Message, bot: Bot):
    chat_id = message.chat.id

    warned = await get_group_warned_count(chat_id)
    banned = await get_group_banned_count(chat_id)
    total = await get_group_total_warnings(chat_id)

    title = escape(message.chat.title or "Noma'lum guruh")
    await message.answer(
        f"📊 <b>{title} — Holat</b>\n\n"
        f"⚠️ Ogohlantirilganlar: <b>{warned}</b> foydalanuvchi\n"
        f"🚫 Bloklanganlar: <b>{banned}</b> foydalanuvchi\n"
        f"📝 Jami ogohlantirishlar: <b>{total}</b>\n\n"
        f"<i>3 bosqichli ogohlantirish tizimi ishlayapti.</i>"
    )


@router.message(F.chat.type.in_({"group", "supergroup"}), _is_apk)
async def handle_apk(message: Message, bot: Bot):
    user = message.from_user
    if not user or user.is_bot:
        return

    chat_id = message.chat.id
    chat_title = message.chat.title or "Noma'lum guruh"
    file_name = message.document.file_name or "apk"

    try:
        await message.delete()
    except Exception as e:
        logger.error(f"APK faylni o'chirishda xato: {e}")
        return

    logger.info(
        f"APK o'chirildi: user={user.id} group={chat_id} file={file_name}"
    )

    try:
        await bot.send_message(
            chat_id,
            f"🧹 <b>APK fayl tozalandi</b>\n\n"
            f"👤 Foydalanuvchi: <b>{escape(user.full_name)}</b>\n"
            f"📁 Fayl: <code>{escape(file_name)}</code>\n\n"
            f"<i>Xavfsizlik sababli APK fayllar o'chiriladi.</i>\n"
            f"<i>Ogohlantirish berilmadi.</i>"
        )
    except Exception as e:
        logger.error(f"APK hisobotini yuborishda xato: {e}")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def check_group_message(message: Message, bot: Bot):
    if not message.text and not message.caption:
        return

    user = message.from_user
    if not user or user.is_bot:
        return

    if _is_apk(message):
        return

    chat_id = message.chat.id
    safe_title = escape(message.chat.title or "Noma'lum guruh")
    user_id = user.id
    text = message.text or message.caption or ""
    safe_name = escape(user.full_name or "")

    if await is_user_admin(bot, chat_id, user_id):
        return

    if await is_blacklisted(user_id):
        try:
            await message.delete()
            await notify_group_admins(
                bot, chat_id, safe_title,
                f"🗑️ <b>Xabar o'chirildi</b>\n\n"
                f"👤 Foydalanuvchi: <b>{safe_name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📋 Sabab: Global qora ro'yxatda\n\n"
                f"<i>Foydalanuvchi avtomatik bloklangan.</i>",
                exclude_user_id=user_id
            )
        except Exception as e:
            logger.error(f"Xabarni o'chirishda xato: {e}")
        return

    if not is_spam(text):
        return

    warn_count = await add_warning(user_id, chat_id)
    logger.info(
        f"WARN: user={user_id} group={chat_id} count={warn_count} text={text[:30]}"
    )

    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Spam xabarni o'chirishda xato: {e}")

    safe_text = escape(text[:100])

    if warn_count == 1:
        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>Ogohlantirish 1/3</b>\n"
                f"👤 {safe_name}\n\n"
                f"Noqonuniy xabar aniqlandi va o'chirildi.\n"
                f"<i>Yana 2 marta qoida buzsangiz, ban bo'lasiz!</i>"
            )
            await log_warning(user_id, chat_id, 1, "warned")
            _track_task(delete_later(warn_msg, 10))

            await notify_group_admins(
                bot, chat_id, safe_title,
                f"⚠️ <b>Ogohlantirish berildi</b>\n\n"
                f"👤 Foydalanuvchi: <b>{safe_name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📝 Ogohlantirish: 1/3\n"
                f"💬 Xabar: <i>{safe_text}</i>",
                exclude_user_id=user_id
            )
        except Exception as e:
            logger.error(f"Ogohlantirish xabarini yuborishda xato: {e}")

    elif warn_count == 2:
        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>Ogohlantirish 2/3</b>\n"
                f"👤 {safe_name}\n\n"
                f"<b>DIQQAT!</b> Yana 1 marta qoida buzsangiz, guruhdan chiqarilasiz!"
            )
            await log_warning(user_id, chat_id, 2, "warned")
            _track_task(delete_later(warn_msg, 10))

            await notify_group_admins(
                bot, chat_id, safe_title,
                f"⚠️ <b>Ogohlantirish 2/3</b>\n\n"
                f"👤 Foydalanuvchi: <b>{safe_name}</b>\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📝 Ogohlantirish: 2/3\n"
                f"❗ Yana 1 marta ban bo'ladi!",
                exclude_user_id=user_id
            )
        except Exception as e:
            logger.error(f"Ogohlantirish xabarini yuborishda xato: {e}")

    elif warn_count >= MAX_WARNINGS:
        try:
            username = user.username or ""
            full_name = user.full_name or ""
            reason = "3 marta qoida buzgan (spam/18+ kontent)"

            await add_to_blacklist(user_id, username, full_name, reason)
            await log_warning(user_id, chat_id, 3, "banned")

            await bot.ban_chat_member(chat_id, user_id)
            await reset_warnings(user_id, chat_id)

            await bot.send_message(
                chat_id,
                f"🚫 <b>BAN!</b>\n"
                f"👤 {escape(full_name)} guruhdan chiqarildi.\n"
                f"📋 Global qora ro'yxatga qo'shildi.\n\n"
                f"<i>Sabab: 3 marta qoida buzgan.</i>"
            )

            await notify_group_admins(
                bot, chat_id, safe_title,
                f"🚫 <b>BAN — Foydalanuvchi chiqarildi</b>\n\n"
                f"👤 Foydalanuvchi: <b>{escape(full_name)}</b> (@{escape(username)})\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📋 Sabab: {escape(reason)}\n\n"
                f"<i>Foydalanuvchi guruhdan chiqarildi va global qora ro'yxatga qo'shildi.</i>",
                exclude_user_id=user_id,
                force=True
            )

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🛡️ <b>Anti-Spam Hisobot</b>\n\n"
                    f"👤 Foydalanuvchi: {escape(full_name)} (@{escape(username)})\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📍 Guruh: {escape(chat_title)}\n"
                    f"📋 Sabab: {escape(reason)}"
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Ban qilishda xato: {e}")


async def delete_later(message: Message, seconds: int):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass
