from collections.abc import Iterator, Sequence
from decimal import Decimal
from urllib.parse import quote

from .checker import CandleMetrics
from .models import LEGACY_LANGUAGE, Alert, AlertSpec, Language, decimal_text


_ADD_EXAMPLES = (
    "/add PEPE price > 0.0000125\n"
    "/add BTC price < 60000\n"
    "/add WIF volume x3\n"
    "/add ORDI move 3%"
)
_LANG_OPTIONS = "/lang en — English\n/lang ru — Русский"

TRANSLATIONS: dict[Language, dict[str, str]] = {
    "ru": {
        "welcome": (
            "Привет! Я отслеживаю фьючерсы Binance USDT-M и сообщаю о срабатывании алертов.\n\n"
            "{add_usage}\n\n"
            "/list — показать алерты\n"
            "/del <номер> — удалить алерт\n"
            "/lang — показать или изменить язык"
        ),
        "add_usage": f"Примеры добавления\n{_ADD_EXAMPLES}",
        "symbol_invalid": "Введи символ фьючерса, например PEPE или PEPEUSDT.",
        "positive_number": "Введи положительное число. Дробную часть можно отделять точкой или запятой.",
        "alert_id_invalid": "Укажи номер из /list. Пример /del 4.",
        "lang_usage": f"Выбери язык одной из команд.\n{_LANG_OPTIONS}",
        "lang_current": f"Текущий язык — русский.\n{_LANG_OPTIONS}",
        "lang_changed": "Язык переключён на русский.",
        "market_unavailable": "Список фьючерсов Binance пока недоступен. Попробуй чуть позже.",
        "symbol_unavailable": "Торгуемый фьючерс {symbol} на Binance USDT-M не найден.",
        "symbol_suggestion": "Доступен {symbol}. Укажи его символ и порог в цене этого контракта.",
        "alert_limit": "Можно держать не больше {limit} включённых алертов. Удали лишние через /del.",
        "alert_added": "Алерт #{alert_id} добавлен.",
        "alert_existing": "Алерт #{alert_id} уже включён.",
        "alert_rearmed": "Алерт #{alert_id} снова включён.",
        "alert_deleted": "Алерт #{alert_id} удалён.",
        "alert_missing": "У тебя нет алерта #{alert_id}.",
        "price_above": "{symbol} · цена выше {value}",
        "price_below": "{symbol} · цена ниже {value}",
        "volume_condition": "{symbol} · объём выше среднего более чем в {value} раза",
        "move_condition": "{symbol} · изменение цены больше {value}% за 5 мин",
        "list_empty": "Алертов пока нет. Добавь первый через /add.",
        "list_title": "Твои алерты",
        "list_more": "Твои алерты · продолжение",
        "alert_disabled": " (выключен)",
        "current_price": "Текущая цена · {price} USDT",
        "change_5m": "За 5 мин · {change}",
        "volume_5m": "Объём 5 мин · ×{multiple:.1f} к среднему",
        "no_data": "нет данных",
        "chart_url": "https://www.binance.com/ru/futures/{symbol}",
    },
    "en": {
        "welcome": (
            "Hi! I track Binance USDT-M futures and send a message when an alert fires.\n\n"
            "{add_usage}\n\n"
            "/list — show your alerts\n"
            "/del <number> — delete an alert\n"
            "/lang — show or change the language"
        ),
        "add_usage": f"Examples of adding an alert\n{_ADD_EXAMPLES}",
        "symbol_invalid": "Enter a futures symbol such as PEPE or PEPEUSDT.",
        "positive_number": "Enter a positive number. Use a dot or a comma as the decimal separator.",
        "alert_id_invalid": "Enter a number from /list. For example, /del 4.",
        "lang_usage": f"Choose a language with one of these commands.\n{_LANG_OPTIONS}",
        "lang_current": f"Current language is English.\n{_LANG_OPTIONS}",
        "lang_changed": "Language switched to English.",
        "market_unavailable": "The Binance futures list is temporarily unavailable. Try again shortly.",
        "symbol_unavailable": "No active Binance USDT-M futures contract found for {symbol}.",
        "symbol_suggestion": "{symbol} is available. Use its symbol and a threshold in that contract's price units.",
        "alert_limit": "You can have up to {limit} enabled alerts. Use /del to remove an alert.",
        "alert_added": "Alert #{alert_id} added.",
        "alert_existing": "Alert #{alert_id} is already enabled.",
        "alert_rearmed": "Alert #{alert_id} enabled again.",
        "alert_deleted": "Alert #{alert_id} deleted.",
        "alert_missing": "You don't have an alert #{alert_id}.",
        "price_above": "{symbol} · price above {value}",
        "price_below": "{symbol} · price below {value}",
        "volume_condition": "{symbol} · volume above {value}× the average",
        "move_condition": "{symbol} · price change greater than {value}% in 5 min",
        "list_empty": "You have no alerts yet. Add one with /add.",
        "list_title": "Your alerts",
        "list_more": "Your alerts · continued",
        "alert_disabled": " (disabled)",
        "current_price": "Current price · {price} USDT",
        "change_5m": "5-min change · {change}",
        "volume_5m": "5-min volume · {multiple:.1f}× the average",
        "no_data": "no data",
        "chart_url": "https://www.binance.com/en/futures/{symbol}",
    },
}


def translate(lang: Language, key: str, /, **values: str | int | Decimal) -> str:
    return TRANSLATIONS[lang][key].format(**values)


def describe(spec: AlertSpec, lang: Language = LEGACY_LANGUAGE) -> str:
    if spec.kind == "price":
        key = "price_above" if spec.op == ">" else "price_below"
    elif spec.kind == "volume":
        key = "volume_condition"
    else:
        key = "move_condition"
    return translate(lang, key, symbol=spec.symbol.removesuffix("USDT"), value=decimal_text(spec.value))


def alert_list(alarms: Sequence[Alert], lang: Language = LEGACY_LANGUAGE) -> Iterator[str]:
    if not alarms:
        yield translate(lang, "list_empty")
        return

    page = translate(lang, "list_title") + "\n"
    for alert in alarms:
        status = "" if alert.active else translate(lang, "alert_disabled")
        line = f"\n#{alert.id} {describe(alert.spec, lang)}{status}"
        if len(page) + len(line) > 3500:
            yield page
            page = translate(lang, "list_more") + "\n"
        page += line
    yield page


def notification(
    spec: AlertSpec, price: Decimal, metrics: CandleMetrics, lang: Language = LEGACY_LANGUAGE
) -> str:
    change = metrics.change_percent
    change_text = translate(lang, "no_data") if change is None else f"{change:+.2f}%"
    lines = [
        describe(spec, lang),
        translate(lang, "current_price", price=decimal_text(price)),
        translate(lang, "change_5m", change=change_text),
    ]
    if metrics.volume_multiple is not None:
        lines.append(translate(lang, "volume_5m", multiple=metrics.volume_multiple))
    lines.append(translate(lang, "chart_url", symbol=quote(spec.symbol, safe="")))
    return "\n".join(lines)
