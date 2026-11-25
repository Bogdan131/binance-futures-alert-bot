import asyncio
import logging
from decimal import Decimal, InvalidOperation
from time import monotonic, time

import httpx

from .checker import CANDLE_LIMIT
from .models import MINUTE_MS, Candle


BASE_URL = "https://fapi.binance.com"
SYMBOL_REFRESH_SECONDS = 3600
SYMBOL_RETRY_SECONDS = 60
KLINE_CACHE_SECONDS = 30
log = logging.getLogger(__name__)


class BinanceMarket:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self.symbols: frozenset[str] | None = None
        self._klines: dict[str, tuple[float, tuple[Candle, ...]]] = {}
        self._kline_slots = asyncio.Semaphore(8)
        self._paused_until = 0.0

    async def _get(self, path: str, params: dict[str, str | int] | None = None) -> object:
        if monotonic() < self._paused_until:
            return None
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status in (418, 429):
                try:
                    delay = int(error.response.headers.get("Retry-After", ""))
                except ValueError:
                    delay = 300 if status == 418 else 60
                self._paused_until = max(self._paused_until, monotonic() + max(1, delay))
            log.warning("Binance %s ответил HTTP %s", path, status)
        except (httpx.RequestError, ValueError) as error:
            log.warning("Binance %s недоступен (%s)", path, type(error).__name__)
        return None

    async def refresh_symbols(self) -> bool:
        data = await self._get("/fapi/v1/exchangeInfo")
        if not isinstance(data, dict) or not isinstance(data.get("symbols"), list):
            return False
        self.symbols = frozenset(
            row["symbol"]
            for row in data["symbols"]
            if isinstance(row, dict)
            and isinstance(row.get("symbol"), str)
            and row.get("quoteAsset") == "USDT"
            and row.get("marginAsset") == "USDT"
            and row.get("status") == "TRADING"
        )
        return True

    async def run_symbol_refresh(self) -> None:
        while True:
            refreshed = await self.refresh_symbols()
            await asyncio.sleep(SYMBOL_REFRESH_SECONDS if refreshed else SYMBOL_RETRY_SECONDS)

    async def ticker_prices(self) -> dict[str, Decimal]:
        data = await self._get("/fapi/v1/ticker/price")
        if not isinstance(data, list):
            return {}

        prices: dict[str, Decimal] = {}
        for row in data:
            if not isinstance(row, dict) or not isinstance(row.get("symbol"), str):
                continue
            price = _market_decimal(row.get("price"))
            if price is not None and price > 0:
                prices[row["symbol"]] = price
        return prices

    async def klines(self, symbol: str) -> tuple[Candle, ...]:
        async with self._kline_slots:
            now = monotonic()
            cached = self._klines.get(symbol)
            if cached is not None and now < cached[0]:
                return cached[1]
            if now < self._paused_until:
                return ()

            next_request = now + KLINE_CACHE_SECONDS
            self._klines[symbol] = (next_request, ())
            end_time = int(time() * 1000) // MINUTE_MS * MINUTE_MS - 1
            data = await self._get(
                "/fapi/v1/klines",
                {"symbol": symbol, "interval": "1m", "limit": CANDLE_LIMIT, "endTime": end_time},
            )
            candles = _closed_candles(data, end_time)
            self._klines[symbol] = (next_request, candles)
            return candles


def _market_decimal(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _closed_candles(data: object, end_time: int) -> tuple[Candle, ...]:
    if not isinstance(data, list):
        return ()

    candles: dict[int, Candle] = {}
    for row in data:
        if not isinstance(row, list) or len(row) < 7:
            continue
        opened, closed = row[0], row[6]
        if (
            not isinstance(opened, int)
            or not isinstance(closed, int)
            or opened < 0
            or opened % MINUTE_MS != 0
            or closed != opened + MINUTE_MS - 1
            or closed > end_time
        ):
            continue

        close, volume = _market_decimal(row[4]), _market_decimal(row[5])
        if close is not None and close > 0 and volume is not None and volume >= 0:
            candles[opened] = Candle(opened, close, volume)

    if end_time - MINUTE_MS + 1 not in candles:
        return ()
    return tuple(candles[opened] for opened in sorted(candles))
