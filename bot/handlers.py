import asyncio
from time import time

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from . import texts
from .commands import MAX_ALERTS_PER_USER, parse_add, parse_alert_id
from .market import BinanceMarket
from .storage import AlertStorage


async def start(message: Message) -> None:
    await message.answer(texts.WELCOME)


async def add_alert(message: Message, command: CommandObject, storage: AlertStorage, market: BinanceMarket) -> None:
    if message.from_user is None:
        return
    try:
        spec = parse_add(command.args)
    except ValueError as error:
        await message.answer(str(error))
        return

    symbols = market.symbols
    if symbols is None:
        await message.answer("Список фьючерсов Binance пока недоступен. Попробуй чуть позже.")
        return
    if spec.symbol not in symbols:
        suggestion = next(
            (f"{prefix}{spec.symbol}" for prefix in ("1000", "10000", "1000000")
             if f"{prefix}{spec.symbol}" in symbols),
            None,
        )
        reply = f"Торгуемый фьючерс {spec.symbol} на Binance USDT-M не найден."
        if suggestion:
            reply += f" Доступен {suggestion}. Укажи его символ и порог в цене этого контракта."
        await message.answer(reply)
        return

    alert_id, status = await asyncio.to_thread(
        storage.add, message.from_user.id, spec, int(time()), MAX_ALERTS_PER_USER
    )
    if status == "limit":
        await message.answer(
            f"Можно держать не больше {MAX_ALERTS_PER_USER} включённых алертов. Удали лишние через /del."
        )
        return
    responses = {
        "added": f"Алерт #{alert_id} добавлен.",
        "existing": f"Алерт #{alert_id} уже включён.",
        "rearmed": f"Алерт #{alert_id} снова включён.",
    }
    await message.answer(f"{responses[status]}\n{texts.describe(spec)}")


async def list_alerts(message: Message, storage: AlertStorage) -> None:
    if message.from_user is None:
        return
    alerts = await asyncio.to_thread(storage.list_for_user, message.from_user.id)
    for page in texts.alert_list(alerts):
        await message.answer(page)


async def delete_alert(message: Message, command: CommandObject, storage: AlertStorage) -> None:
    if message.from_user is None:
        return
    try:
        alert_id = parse_alert_id(command.args)
    except ValueError as error:
        await message.answer(str(error))
        return

    deleted = await asyncio.to_thread(storage.delete, message.from_user.id, alert_id)
    await message.answer(f"Алерт #{alert_id} удалён." if deleted else f"У тебя нет алерта #{alert_id}.")


def build_router() -> Router:
    router = Router()
    router.message.filter(F.chat.type == ChatType.PRIVATE)
    router.message.register(start, CommandStart())
    router.message.register(add_alert, Command("add"))
    router.message.register(list_alerts, Command("list"))
    router.message.register(delete_alert, Command("del"))
    return router
