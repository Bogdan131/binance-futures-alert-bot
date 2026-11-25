from decimal import Decimal

import pytest

from bot.handlers import parse_add
from bot.models import AlertSpec


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
