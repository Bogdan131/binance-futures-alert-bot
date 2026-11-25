from collections.abc import Iterator, Sequence
from decimal import Decimal
from urllib.parse import quote

from .models import Alert, AlertSpec, decimal_text


ADD_USAGE = (
    "Примеры добавления\n"
    "/add PEPE price > 0.0000125\n"
    "/add BTC price < 60000\n"
    "/add WIF volume x3\n"
    "/add ORDI move 3%"
)

WELCOME = (
    "Привет! Я отслеживаю фьючерсы Binance USDT-M и сообщаю о срабатывании алертов.\n\n"
    f"{ADD_USAGE}\n\n"
    "/list — показать алерты\n"
    "/del <номер> — удалить алерт"
)


def describe(spec: AlertSpec) -> str:
    symbol = spec.symbol.removesuffix("USDT")
    value = decimal_text(spec.value)
    if spec.kind == "price":
        direction = "выше" if spec.op == ">" else "ниже"
        return f"{symbol} · цена {direction} {value}"
    if spec.kind == "volume":
        return f"{symbol} · объём выше среднего более чем в {value} раза"
    return f"{symbol} · изменение цены больше {value}% за 5 мин"


def alert_list(alarms: Sequence[Alert]) -> Iterator[str]:
    if not alarms:
        yield "Алертов пока нет. Добавь первый через /add."
        return

    page = "Твои алерты\n"
    for alert in alarms:
        status = "" if alert.active else " (выключен)"
        line = f"\n#{alert.id} {describe(alert.spec)}{status}"
        if len(page) + len(line) > 3500:
            yield page
            page = "Твои алерты · продолжение\n"
        page += line
    yield page


def notification(spec: AlertSpec, price: Decimal, change_percent: Decimal | None) -> str:
    change = "нет данных" if change_percent is None else f"{change_percent:+.2f}%"
    url = "https://www.binance.com/ru/futures/" + quote(spec.symbol, safe="")
    return (
        f"{describe(spec)}\n"
        f"Текущая цена · {decimal_text(price)} USDT\n"
        f"За 5 мин · {change}\n"
        f"{url}"
    )
