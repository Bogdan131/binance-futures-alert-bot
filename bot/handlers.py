import asyncio
import re
from decimal import Decimal
from time import time

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from . import texts
from .market import BinanceMarket
from .models import AlertSpec
from .storage import AlertStorage


_SYMBOL = re.compile(r"[^\W_]+(?:USDT_[0-9]{6})?")
_POSITIVE_NUMBER = re.compile(r"(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)")


def _number(text: str) -> Decimal:
    if len(text) <= 64 and _POSITIVE_NUMBER.fullmatch(text):
        value = Decimal(text.replace(",", "."))
        if value > 0:
            return value
    raise ValueError("Введи положительное число. Дробную часть можно отделять точкой или запятой.")


def parse_add(arguments: str | None) -> AlertSpec:
    """Parse the arguments aiogram extracts from /add."""
    parts = (arguments or "").split()
    if len(parts) < 2:
        raise ValueError(texts.ADD_USAGE)

    symbol, kind, *args = parts
    symbol = symbol.upper()
    if len(symbol) > 64 or not _SYMBOL.fullmatch(symbol):
        raise ValueError("Введи символ фьючерса, например PEPE или PEPEUSDT.")
    if not symbol.endswith("USDT") and "_" not in symbol:
        symbol += "USDT"

    kind = kind.lower()
    if kind == "price" and len(args) == 2 and args[0] in (">", "<"):
        op = ">" if args[0] == ">" else "<"
        return AlertSpec(symbol, "price", op, _number(args[1]))
    if kind == "volume" and len(args) == 1 and args[0][:1].lower() == "x":
        return AlertSpec(symbol, "volume", ">", _number(args[0][1:]))
    if kind == "move" and len(args) == 1 and args[0].endswith("%"):
        return AlertSpec(symbol, "move", ">", _number(args[0][:-1]))
    raise ValueError(texts.ADD_USAGE)


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

    alert_id, status = await asyncio.to_thread(storage.add, message.from_user.id, spec, int(time()))
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
    number = (command.args or "").strip()
    if not (1 <= len(number) <= 19 and number.isascii() and number.isdecimal()):
        await message.answer("Укажи номер из /list. Пример /del 4.")
        return
    alert_id = int(number)
    if not 0 < alert_id < 2**63:
        await message.answer("Укажи номер из /list. Пример /del 4.")
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
