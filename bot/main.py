import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from aiogram.utils.token import TokenValidationError, validate_token
from dotenv import load_dotenv

from .handlers import build_router
from .market import BASE_URL, BinanceMarket
from .service import AlertMonitor
from .storage import AlertStorage


log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    check_seconds: int
    cooldown_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(".env")
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Добавь BOT_TOKEN в .env. Пример находится в .env.example.")
        try:
            validate_token(token)
        except TokenValidationError as error:
            raise ValueError("BOT_TOKEN имеет неверный формат. Проверь токен из @BotFather.") from error
        return cls(token, _positive_int("CHECK_SECONDS", 10), _positive_int("COOLDOWN_MINUTES", 15))


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} должен быть положительным целым числом.") from error
    if value <= 0:
        raise ValueError(f"{name} должен быть положительным целым числом.")
    return value


async def _wait_for_telegram(bot: Bot) -> None:
    delay = 1
    while True:
        try:
            await bot.me()
            return
        except TelegramRetryAfter as error:
            pause = error.retry_after
        except (TelegramNetworkError, TelegramServerError):
            pause = delay
            delay = min(30, delay * 2)
        log.warning("Telegram пока недоступен. Повтор через %s с.", pause)
        await asyncio.sleep(pause)


async def main(settings: Settings) -> None:
    storage = AlertStorage(Path("data") / "alerts.sqlite3")
    await asyncio.to_thread(storage.initialize)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router())

    async with (
        Bot(settings.bot_token) as bot,
        httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(5, connect=3)) as client,
    ):
        market = BinanceMarket(client)
        monitor = AlertMonitor(bot, storage, market, settings.cooldown_minutes * 60)
        async with asyncio.TaskGroup() as tasks:
            refresh_task = tasks.create_task(market.run_symbol_refresh())
            await _wait_for_telegram(bot)
            monitor_task = tasks.create_task(monitor.run(settings.check_seconds))
            try:
                await dispatcher.start_polling(
                    bot,
                    storage=storage,
                    market=market,
                    allowed_updates=dispatcher.resolve_used_update_types(),
                    close_bot_session=False,
                )
            finally:
                monitor_task.cancel()
                refresh_task.cancel()


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env()
    except ValueError as error:
        raise SystemExit(str(error)) from None

    try:
        asyncio.run(main(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
