import asyncio
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip("aiogram")

from aiogram import Bot  # noqa: E402
from aiogram.filters import CommandObject  # noqa: E402
from aiogram.types import Message, User  # noqa: E402

from bot.handlers import add_alert, build_router, change_language, delete_alert, list_alerts, start  # noqa: E402
from bot.main import Settings  # noqa: E402
from bot.market import BinanceMarket  # noqa: E402
from bot.models import AlertSpec  # noqa: E402
from bot.service import AlertMonitor  # noqa: E402
from bot.storage import AlertStorage  # noqa: E402


def test_router_registers_commands() -> None:
    assert [handler.callback for handler in build_router().message.handlers] == [
        start, add_alert, list_alerts, delete_alert, change_language,
    ]


def test_settings_require_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "")
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        Settings.from_env()


def test_language_choice_is_saved_and_used_for_replies(tmp_path: Path) -> None:
    storage = AlertStorage(tmp_path / "alerts.sqlite3")
    storage.initialize()
    message = Mock(spec=Message)
    message.from_user = User(id=123, is_bot=False, first_name="User", language_code="uk-UA")
    message.answer = AsyncMock()

    async def check() -> None:
        await start(message, storage)
        assert storage.get_language(123) == "ru"
        assert message.answer.await_args.args[0].startswith("Привет!")

        await change_language(message, CommandObject(prefix="/", command="lang"), storage)
        assert "Текущий язык — русский." in message.answer.await_args.args[0]
        assert "/lang en" in message.answer.await_args.args[0]

        await change_language(message, CommandObject(prefix="/", command="lang", args="en"), storage)
        assert storage.get_language(123) == "en"
        assert message.answer.await_args.args[0] == "Language switched to English."

        await start(message, storage)
        assert storage.get_language(123) == "en"
        assert message.answer.await_args.args[0].startswith("Hi!")

        await change_language(message, CommandObject(prefix="/", command="lang", args="de"), storage)
        assert "Choose a language" in message.answer.await_args.args[0]
        assert storage.get_language(123) == "en"

        await add_alert(
            message, CommandObject(prefix="/", command="add", args="BTC price > 0"),
            storage, Mock(spec=BinanceMarket),
        )
        assert message.answer.await_args.args[0].startswith("Enter a positive number.")

        await delete_alert(message, CommandObject(prefix="/", command="del", args="0"), storage)
        assert message.answer.await_args.args[0].startswith("Enter a number from /list.")

        await change_language(message, CommandObject(prefix="/", command="lang", args="ru"), storage)
        assert storage.get_language(123) == "ru"
        assert message.answer.await_args.args[0] == "Язык переключён на русский."

    asyncio.run(check())


def test_monitor_uses_each_alert_owners_language(tmp_path: Path) -> None:
    storage = AlertStorage(tmp_path / "alerts.sqlite3")
    storage.initialize()
    storage.set_language(1, "en")
    storage.set_language(2, "ru")
    spec = AlertSpec("BTCUSDT", "price", ">", Decimal(1))
    for user_id in (1, 2, 3):
        storage.add(user_id, spec, now=10)

    market = Mock(spec=BinanceMarket)
    market.symbols = {"BTCUSDT"}
    market.ticker_prices.return_value = {"BTCUSDT": Decimal(100)}
    market.klines.return_value = ()
    bot = Mock(spec=Bot)
    monitor = AlertMonitor(bot, storage, market, cooldown_seconds=900)

    asyncio.run(monitor.check_once())

    assert bot.send_message.await_count == 3
    messages = {call.args[0]: call.args[1] for call in bot.send_message.await_args_list}
    assert messages[1].startswith("BTC · price above 1")
    assert messages[1].endswith("https://www.binance.com/en/futures/BTCUSDT")
    assert messages[2].startswith("BTC · цена выше 1")
    assert messages[2].endswith("https://www.binance.com/ru/futures/BTCUSDT")
    assert messages[3] == messages[2]
