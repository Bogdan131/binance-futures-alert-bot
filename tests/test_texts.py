from decimal import Decimal

from bot.checker import CandleMetrics
from bot.models import AlertSpec
from bot.texts import notification


def test_volume_notification_shows_multiple() -> None:
    text = notification(
        AlertSpec("WIFUSDT", "volume", ">", Decimal(3)),
        Decimal("2.4500"),
        CandleMetrics(Decimal("1.234"), Decimal("4.26")),
    )
    assert text.splitlines() == [
        "WIF · объём выше среднего более чем в 3 раза",
        "Текущая цена · 2.45 USDT",
        "За 5 мин · +1.23%",
        "Объём 5 мин · ×4.3 к среднему",
        "https://www.binance.com/ru/futures/WIFUSDT",
    ]


def test_notification_without_candles() -> None:
    text = notification(
        AlertSpec("BTCUSDT", "price", "<", Decimal(60000)), Decimal(59999), CandleMetrics(None, None)
    )
    assert "За 5 мин · нет данных" in text
    assert "Объём" not in text
