import asyncio
import logging
from time import monotonic, time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions

from .checker import candle_metrics, condition_met, cooldown_ready
from .market import BinanceMarket
from .storage import AlertStorage
from .texts import notification


log = logging.getLogger(__name__)


class AlertMonitor:
    def __init__(
        self, bot: Bot, storage: AlertStorage, market: BinanceMarket, cooldown_seconds: int
    ) -> None:
        self._bot = bot
        self._storage = storage
        self._market = market
        self._cooldown_seconds = cooldown_seconds
        self._telegram_paused_until = 0.0

    async def run(self, interval: int) -> None:
        while True:
            started_at = monotonic()
            try:
                await self.check_once()
            except Exception:
                log.exception("Сбой цикла проверки алертов, повтор в следующем цикле")
            await asyncio.sleep(max(0, interval - (monotonic() - started_at)))

    async def check_once(self) -> None:
        prices = await self._market.ticker_prices()
        if not prices or monotonic() < self._telegram_paused_until:
            return

        alerts = await asyncio.to_thread(self._storage.list_active)
        available = self._market.symbols
        now = int(time())
        candidates = [
            alert
            for alert in alerts
            if alert.spec.symbol in prices
            and (available is None or alert.spec.symbol in available)
            and cooldown_ready(alert.last_fired_at, now, self._cooldown_seconds)
            and (
                alert.spec.kind != "price"
                or condition_met(alert.spec, prices[alert.spec.symbol])
            )
        ]

        symbols = sorted({alert.spec.symbol for alert in candidates})
        batches = await asyncio.gather(*(self._market.klines(symbol) for symbol in symbols))
        metrics = {symbol: candle_metrics(candles) for symbol, candles in zip(symbols, batches)}

        for alert in candidates:
            spec = alert.spec
            price = prices[spec.symbol]
            indicators = metrics[spec.symbol]
            if not condition_met(spec, price, indicators):
                continue

            attempted_at = int(time())
            claimed = await asyncio.to_thread(
                self._storage.claim, alert, attempted_at, self._cooldown_seconds
            )
            if not claimed:
                continue

            rearm = spec.kind == "price"
            try:
                await self._bot.send_message(
                    alert.user_id,
                    notification(spec, price, indicators),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                rearm = False
            except TelegramForbiddenError:
                disabled = await asyncio.to_thread(self._storage.deactivate_user, alert.user_id)
                log.info("Пользователь заблокировал бота, выключено алертов: %s", disabled)
                rearm = False
            except TelegramAPIError as error:
                log.warning("Не удалось отправить алерт #%s (%s)", alert.id, type(error).__name__)
                if isinstance(error, TelegramRetryAfter):
                    self._telegram_paused_until = monotonic() + error.retry_after
            finally:
                if rearm:
                    await asyncio.to_thread(self._storage.rearm_after_send_error, alert.id, attempted_at)

            if monotonic() < self._telegram_paused_until:
                return
