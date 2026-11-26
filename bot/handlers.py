import asyncio
from time import time

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, User

from . import texts
from .commands import (
    MAX_ALERTS_PER_USER,
    CommandError,
    default_language,
    parse_add,
    parse_alert_id,
    parse_lang,
)
from .market import BinanceMarket
from .models import Language
from .storage import AlertStorage


async def _user_language(user: User, storage: AlertStorage) -> Language:
    """Saved language, or one chosen from the Telegram app language when the user skipped /start."""
    return await asyncio.to_thread(
        storage.get_or_create_language, user.id, default_language(user.language_code)
    )


async def start(message: Message, storage: AlertStorage) -> None:
    user = message.from_user
    if user is None:
        return
    lang = await asyncio.to_thread(
        storage.get_or_create_language, user.id, default_language(user.language_code)
    )
    await message.answer(texts.translate(lang, "welcome", add_usage=texts.translate(lang, "add_usage")))


async def change_language(message: Message, command: CommandObject, storage: AlertStorage) -> None:
    user = message.from_user
    if user is None:
        return
    try:
        requested = parse_lang(command.args)
    except CommandError as error:
        lang = await _user_language(user, storage)
        await message.answer(texts.translate(lang, error.key))
        return

    if requested is None:
        lang = await _user_language(user, storage)
        await message.answer(texts.translate(lang, "lang_current"))
        return

    await asyncio.to_thread(storage.set_language, user.id, requested)
    await message.answer(texts.translate(requested, "lang_changed"))


async def add_alert(message: Message, command: CommandObject, storage: AlertStorage, market: BinanceMarket) -> None:
    user = message.from_user
    if user is None:
        return
    lang = await _user_language(user, storage)
    try:
        spec = parse_add(command.args)
    except CommandError as error:
        await message.answer(texts.translate(lang, error.key))
        return

    symbols = market.symbols
    if symbols is None:
        await message.answer(texts.translate(lang, "market_unavailable"))
        return
    if spec.symbol not in symbols:
        suggestion = next(
            (f"{prefix}{spec.symbol}" for prefix in ("1000", "10000", "1000000")
             if f"{prefix}{spec.symbol}" in symbols),
            None,
        )
        reply = texts.translate(lang, "symbol_unavailable", symbol=spec.symbol)
        if suggestion:
            reply += " " + texts.translate(lang, "symbol_suggestion", symbol=suggestion)
        await message.answer(reply)
        return

    alert_id, status = await asyncio.to_thread(
        storage.add, user.id, spec, int(time()), MAX_ALERTS_PER_USER
    )
    if status == "limit":
        await message.answer(texts.translate(lang, "alert_limit", limit=MAX_ALERTS_PER_USER))
        return

    reply = texts.translate(lang, f"alert_{status}", alert_id=alert_id)
    await message.answer(f"{reply}\n{texts.describe(spec, lang)}")


async def list_alerts(message: Message, storage: AlertStorage) -> None:
    user = message.from_user
    if user is None:
        return
    lang = await _user_language(user, storage)
    alerts = await asyncio.to_thread(storage.list_for_user, user.id)
    for page in texts.alert_list(alerts, lang):
        await message.answer(page)


async def delete_alert(message: Message, command: CommandObject, storage: AlertStorage) -> None:
    user = message.from_user
    if user is None:
        return
    lang = await _user_language(user, storage)
    try:
        alert_id = parse_alert_id(command.args)
    except CommandError as error:
        await message.answer(texts.translate(lang, error.key))
        return

    deleted = await asyncio.to_thread(storage.delete, user.id, alert_id)
    key = "alert_deleted" if deleted else "alert_missing"
    await message.answer(texts.translate(lang, key, alert_id=alert_id))


def build_router() -> Router:
    router = Router()
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    router.message.register(start, CommandStart())
    router.message.register(add_alert, Command("add"))
    router.message.register(list_alerts, Command("list"))
    router.message.register(delete_alert, Command("del"))
    router.message.register(change_language, Command("lang"))
    return router
