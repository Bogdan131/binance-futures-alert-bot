import re
from decimal import Decimal

from . import texts
from .models import AlertSpec


MAX_ALERTS_PER_USER = 50
_ALERT_ID = re.compile(r"[0-9]{1,19}")

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


def parse_alert_id(arguments: str | None) -> int:
    """Parse the alert number for /del."""
    number = (arguments or "").strip()
    if _ALERT_ID.fullmatch(number):
        alert_id = int(number)
        if 0 < alert_id < 2**63:
            return alert_id
    raise ValueError("Укажи номер из /list. Пример /del 4.")
