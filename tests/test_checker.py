from dataclasses import replace
from decimal import Decimal

import pytest

from bot.checker import candle_metrics, condition_met, cooldown_ready
from bot.models import MINUTE_MS, AlertSpec, Candle, Operator


@pytest.mark.parametrize(
    ("op", "price", "fired"),
    [
        (">", "0.0000126", True),
        (">", "0.0000125", False),
        (">", "0.0000124", False),
        ("<", "0.0000124", True),
        ("<", "0.0000125", False),
        ("<", "0.0000126", False),
    ],
)
def test_price(op: Operator, price: str, fired: bool) -> None:
    spec = AlertSpec("PEPEUSDT", "price", op, Decimal("0.0000125"))
    assert condition_met(spec, Decimal(price)) is fired


@pytest.mark.parametrize(("recent_volume", "fired"), [(29, False), (30, False), (31, True)])
def test_volume(recent_volume: int, fired: bool) -> None:
    candles = [
        Candle(i * MINUTE_MS, Decimal(100), Decimal(10 if i < 120 else recent_volume))
        for i in range(125)
    ]
    metrics = candle_metrics(candles)
    assert metrics.volume_multiple == Decimal(recent_volume) / 10
    spec = AlertSpec("WIFUSDT", "volume", ">", Decimal(3))
    assert condition_met(spec, Decimal(100), metrics) is fired


@pytest.mark.parametrize(
    ("last_close", "expected_change", "fired"),
    [("103.2", "3.2", True), ("96.8", "-3.2", True), ("103", "3", False), ("97", "-3", False)],
)
def test_move(last_close: str, expected_change: str, fired: bool) -> None:
    candles = [Candle(i * MINUTE_MS, Decimal(100), Decimal(1)) for i in range(6)]
    candles[-1] = replace(candles[-1], close=Decimal(last_close))
    metrics = candle_metrics(candles)
    assert metrics.change_percent == Decimal(expected_change)
    spec = AlertSpec("ORDIUSDT", "move", ">", Decimal(3))
    assert condition_met(spec, Decimal(last_close), metrics) is fired


def test_missing_candles_do_not_make_signals() -> None:
    candles = [Candle(i * MINUTE_MS, Decimal(100), Decimal(1)) for i in range(125)]
    assert candle_metrics(candles[1:]).volume_multiple is None
    assert candle_metrics(candles[-5:]).change_percent is None
    assert candle_metrics(candles[:-4] + candles[-3:]).change_percent is None
    zero_baseline = [replace(row, volume=Decimal(0)) for row in candles[:120]]
    assert candle_metrics(zero_baseline + candles[120:]).volume_multiple is None


@pytest.mark.parametrize(("last", "now", "ready"), [(None, 0, True), (10, 909, False), (10, 910, True)])
def test_cooldown(last: int | None, now: int, ready: bool) -> None:
    assert cooldown_ready(last, now, cooldown_seconds=900) is ready
