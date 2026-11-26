import re
from decimal import Decimal

from .models import LANGUAGES, AlertSpec, Language


MAX_ALERTS_PER_USER = 50
_ALERT_ID = re.compile(r"[0-9]{1,19}")

_SYMBOL = re.compile(r"[^\W_]+(?:USDT_[0-9]{6})?")
_POSITIVE_NUMBER = re.compile(r"(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)")


class CommandError(ValueError):
    """A command validation error with a translation key."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def default_language(language_code: str | None) -> Language:
    code = (language_code or "").lower()
    if code.startswith("uk"):
        return "uk"
    return "ru" if code.startswith("ru") else "en"


def parse_lang(arguments: str | None) -> Language | None:
    """Return None when /lang was sent without a language."""
    lang = (arguments or "").strip().lower()
    if not lang:
        return None
    if lang == "ua":
        return "uk"
    if lang in LANGUAGES:
        return lang  # type: ignore[return-value]
    raise CommandError("lang_usage")


def _number(text: str) -> Decimal:
    if len(text) <= 64 and _POSITIVE_NUMBER.fullmatch(text):
        value = Decimal(text.replace(",", "."))
        if value > 0:
            return value
    raise CommandError("positive_number")


def parse_add(arguments: str | None) -> AlertSpec:
    """Parse the arguments aiogram extracts from /add."""
    parts = (arguments or "").split()
    if len(parts) < 2:
        raise CommandError("add_usage")

    symbol, kind, *args = parts
    symbol = symbol.upper()
    if len(symbol) > 64 or not _SYMBOL.fullmatch(symbol):
        raise CommandError("symbol_invalid")
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
    raise CommandError("add_usage")


def parse_alert_id(arguments: str | None) -> int:
    """Parse the alert number for /del."""
    number = (arguments or "").strip()
    if _ALERT_ID.fullmatch(number):
        alert_id = int(number)
        if 0 < alert_id < 2**63:
            return alert_id
    raise CommandError("alert_id_invalid")
