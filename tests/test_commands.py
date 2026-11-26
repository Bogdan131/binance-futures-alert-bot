from decimal import Decimal

import pytest

from bot.commands import CommandError, default_language, parse_add, parse_alert_id, parse_lang
from bot.models import AlertSpec, Language


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ("PEPE price > 0.0000125", AlertSpec("PEPEUSDT", "price", ">", Decimal("0.0000125"))),
        ("  pepeusdt   price < 0.0000125 ", AlertSpec("PEPEUSDT", "price", "<", Decimal("0.0000125"))),
        ("wif volume x3", AlertSpec("WIFUSDT", "volume", ">", Decimal(3))),
        ("ORDI move 3%", AlertSpec("ORDIUSDT", "move", ">", Decimal(3))),
        ("1000pepe Price > .0125", AlertSpec("1000PEPEUSDT", "price", ">", Decimal(".0125"))),
        ("btcusdt_261225 move 1,5%", AlertSpec("BTCUSDT_261225", "move", ">", Decimal("1.5"))),
    ],
)
def test_parse_add(arguments: str, expected: AlertSpec) -> None:
    assert parse_add(arguments) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        None,
        "",
        "BTC",
        "BTCUSDT price",
        "BTC/USDT price > 1",
        "BTC price >= 2",
        "BTC price > 2 extra",
        "BTC price < 0",
        "BTC price > NaN",
        "BTC price > Infinity",
        "BTC price > 1.2.3",
        "WIF volume 3",
        "WIF volume x",
        "WIF volume x-3",
        "ORDI move 3",
        "ORDI move -3%",
        "ORDI move 0%",
        "BTC funding 1%",
    ],
)
def test_parse_add_invalid(arguments: str | None) -> None:
    with pytest.raises(ValueError):
        parse_add(arguments)


def test_parse_alert_id() -> None:
    assert parse_alert_id(" 4 ") == 4


@pytest.mark.parametrize("arguments", [None, "", "0", "-1", "4a", "٤", "1" * 20, str(2**63)])
def test_parse_alert_id_invalid(arguments: str | None) -> None:
    with pytest.raises(ValueError):
        parse_alert_id(arguments)


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [(None, None), ("", None), ("  ", None), ("en", "en"), (" RU ", "ru"), ("uk", "uk"), ("UA", "uk")],
)
def test_parse_lang(arguments: str | None, expected: Language | None) -> None:
    assert parse_lang(arguments) == expected


@pytest.mark.parametrize("arguments", ["de", "en ru", "en-US"])
def test_parse_lang_invalid_returns_translation_key(arguments: str) -> None:
    with pytest.raises(CommandError) as raised:
        parse_lang(arguments)
    assert raised.value.key == "lang_usage"


@pytest.mark.parametrize(
    ("language_code", "expected"),
    [("ru", "ru"), ("RU-ru", "ru"), ("uk", "uk"), ("uk-UA", "uk"),
     ("en-US", "en"), ("de", "en"), ("", "en"), (None, "en")],
)
def test_default_language(language_code: str | None, expected: Language) -> None:
    assert default_language(language_code) == expected
