from decimal import Decimal
from string import Formatter

import pytest

from bot.checker import CandleMetrics
from bot.models import Alert, AlertSpec, Language
from bot.texts import TRANSLATIONS, alert_list, notification


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


@pytest.mark.parametrize(
    ("lang", "change", "volume_label"),
    [("ru", "За 5 мин · нет данных", "Объём"), ("en", "5-min change · no data", "5-min volume")],
)
def test_notification_without_candles(lang: Language, change: str, volume_label: str) -> None:
    text = notification(
        AlertSpec("BTCUSDT", "price", "<", Decimal(60000)), Decimal(59999),
        CandleMetrics(None, None), lang=lang,
    )
    assert change in text
    assert volume_label not in text


def test_english_notification_shows_volume_and_english_chart() -> None:
    text = notification(
        AlertSpec("WIFUSDT", "volume", ">", Decimal(3)),
        Decimal("2.4500"),
        CandleMetrics(Decimal("1.234"), Decimal("4.26")),
        lang="en",
    )
    assert text.splitlines() == [
        "WIF · volume above 3× the average",
        "Current price · 2.45 USDT",
        "5-min change · +1.23%",
        "5-min volume · 4.3× the average",
        "https://www.binance.com/en/futures/WIFUSDT",
    ]


@pytest.mark.parametrize(
    ("lang", "title", "entry", "empty"),
    [
        ("ru", "Твои алерты", "#7 BTC · цена выше 1 (выключен)", "Алертов пока нет."),
        ("en", "Your alerts", "#7 BTC · price above 1 (disabled)", "You have no alerts yet."),
    ],
)
def test_list_is_localized(lang: Language, title: str, entry: str, empty: str) -> None:
    alert = Alert(7, 100, AlertSpec("BTCUSDT", "price", ">", Decimal(1)), False, 20, 10)
    assert list(alert_list([alert], lang)) == [f"{title}\n\n{entry}"]
    assert next(alert_list([], lang)).startswith(empty)


def test_translation_keys_and_placeholders_match() -> None:
    ru, en = TRANSLATIONS["ru"], TRANSLATIONS["en"]
    assert ru.keys() == en.keys()
    formatter = Formatter()
    for key in ru:
        ru_fields = {name for _, name, _, _ in formatter.parse(ru[key]) if name is not None}
        en_fields = {name for _, name, _, _ in formatter.parse(en[key]) if name is not None}
        assert ru_fields == en_fields, key
