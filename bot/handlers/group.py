import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, Command

from bot.database.queries import (
    add_group, remove_group, is_blacklisted,
    log_warning, add_to_blacklist,
    get_group_warned_count, get_group_banned_count, get_group_total_warnings
)
from bot.utils.anti_spam import is_spam, add_warning, get_warning_count, reset_warnings
from bot.config import ADMIN_ID

router = Router()
logger = logging.getLogger(__name__)

MAX_WARNINGS = 3


async def is_user_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


@router.chat_member(ChatMemberUpdatedFilter(
    member_status_changed=IS_NOT_MEMBER >> IS_MEMBER
))
async def on_bot_added(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in ("group", "supergroup"):
        await add_group(chat.id, chat.title)
        logger.info(f"Bot guruhga qo'shildi: {chat.title} ({chat.id})")

        await event.answer(
            f"🛡️ <b>Guruhmaster Bot</b> muvaffaqiyatli qo'shildi!\n\n"
            f"Men bu guruhdagi spam va noqonuniy xabarlarni avtomatik tozalayman.\n"
            f"<i>Admin huquqlari talab qilinadi.</i>",
            parse_mode="HTML"
        )


@router.message(Command("status"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_status(message: Message, bot: Bot):
    chat_id = message.chat.id

    warned = await get_group_warned_count(chat_id)
    banned = await get_group_banned_count(chat_id)
    total = await get_group_total_warnings(chat_id)

    await message.answer(
        f"📊 <b>{message.chat.title} — Holat</b>\n\n"
        f"⚠️ Ogohlantirilganlar: <b>{warned}</b> foydalanuvchi\n"
        f"🚫 Bloklanganlar: <b>{banned}</b> foydalanuvchi\n"
        f"📝 Jami ogohlantirishlar: <b>{total}</b>\n\n"
        f"<i>3 bosqichli ogohlantirish tizimi ishlayapti.</i>",
        parse_mode="HTML"
    )


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def check_group_message(message: Message, bot: Bot):
    if not message.text and not message.caption:
        return

    user = message.from_user
    if not user or user.is_bot:
        return

    chat_id = message.chat.id
    user_id = user.id
    text = message.text or message.caption or ""

    if await is_user_admin(bot, chat_id, user_id):
        return

    if await is_blacklisted(user_id):
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Xabarni o'chirishda xato: {e}")
        return

    if not is_spam(text):
        return

    warn_count = add_warning(user_id, chat_id)
    logger.info(f"WARN: user={user_id} group={chat_id} count={warn_count} text={text[:30]}")

    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Spam xabarni o'chirishda xato: {e}")

    if warn_count == 1:
        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>Ogohlantirish 1/3</b>\n"
                f"👤 {user.full_name}\n\n"
                f"Noqonuniy xabar aniqlandi va o'chirildi.\n"
                f"<i>Yana 2 marta qoida buzsangiz, ban bo'lasiz!</i>",
                parse_mode="HTML"
            )
            await log_warning(user_id, chat_id, 1, "warned")
            asyncio.create_task(delete_later(warn_msg, 10))
        except Exception as e:
            logger.error(f"Ogohlantirish xabarini yuborishda xato: {e}")

    elif warn_count == 2:
        try:
            warn_msg = await bot.send_message(
                chat_id,
                f"⚠️ <b>Ogohlantirish 2/3</b>\n"
                f"👤 {user.full_name}\n\n"
                f"<b>DIQQAT!</b> Yana 1 marta qoida buzsangiz, guruhdan chiqarilasiz!",
                parse_mode="HTML"
            )
            await log_warning(user_id, chat_id, 2, "warned")
            asyncio.create_task(delete_later(warn_msg, 10))
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
            reset_warnings(user_id, chat_id)

            await bot.send_message(
                chat_id,
                f"🚫 <b>BAN!</b>\n"
                f"👤 {full_name} guruhdan chiqarildi.\n"
                f"📋 Global qora ro'yxatga qo'shildi.\n\n"
                f"<i>Sabab: 3 marta qoida buzgan.</i>",
                parse_mode="HTML"
            )

            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"🛡️ <b>Anti-Spam Hisobot</b>\n\n"
                    f"👤 Foydalanuvchi: {full_name} (@{username})\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📍 Guruh: {message.chat.title}\n"
                    f"📋 Sabab: {reason}",
                    parse_mode="HTML"
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
