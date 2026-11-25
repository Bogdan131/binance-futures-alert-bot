import asyncio
from decimal import Decimal

import httpx
import pytest

from bot import market
from bot.models import MINUTE_MS


def test_klines_use_closed_minutes_and_one_request_per_30_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_minute = 1000 * MINUTE_MS
    clock = 100.0
    monkeypatch.setattr(market, "monotonic", lambda: clock)
    monkeypatch.setattr(market, "time", lambda: (current_minute + 25_000) / 1000)
    calls: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        rows = [
            [i * MINUTE_MS, "1", "1", "1", "1.25", "10", (i + 1) * MINUTE_MS - 1]
            for i in range(875, 1001)
        ]
        return httpx.Response(200, json=rows)

    async def check() -> None:
        nonlocal clock
        async with httpx.AsyncClient(base_url=market.BASE_URL, transport=httpx.MockTransport(reply)) as client:
            source = market.BinanceMarket(client)
            candles = await source.klines("WIFUSDT")
            assert len(candles) == 125
            assert candles[-1].open_time_ms == current_minute - MINUTE_MS
            assert candles[-1].close == Decimal("1.25")
            assert calls[0].url.path == "/fapi/v1/klines"
            assert dict(calls[0].url.params) == {
                "symbol": "WIFUSDT", "interval": "1m", "limit": "125", "endTime": str(current_minute - 1)
            }
            clock += 29
            assert await source.klines("WIFUSDT") == candles
            assert len(calls) == 1
            clock += 1
            assert await source.klines("WIFUSDT") == candles
            assert len(calls) == 2

    asyncio.run(check())


def test_symbol_filter_keeps_last_good_list_during_outage() -> None:
    calls: list[str] = []
    contract = {"quoteAsset": "USDT", "marginAsset": "USDT", "status": "TRADING"}

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) > 1:
            raise httpx.ReadTimeout("offline", request=request)
        return httpx.Response(200, json={"symbols": [
            {**contract, "symbol": "1000PEPEUSDT"},
            {**contract, "symbol": "BTCUSDC", "quoteAsset": "USDC"},
            {**contract, "symbol": "ETHUSDT", "status": "PENDING_TRADING"},
        ]})

    async def check() -> None:
        async with httpx.AsyncClient(base_url=market.BASE_URL, transport=httpx.MockTransport(reply)) as client:
            source = market.BinanceMarket(client)
            assert await source.refresh_symbols()
            assert source.symbols == {"1000PEPEUSDT"}
            assert not await source.refresh_symbols()
            assert source.symbols == {"1000PEPEUSDT"}

    asyncio.run(check())
    assert calls == ["/fapi/v1/exchangeInfo"] * 2


def test_binance_rate_limit_pauses_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = 100.0
    monkeypatch.setattr(market, "monotonic", lambda: clock)
    calls: list[str] = []

    def reply(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "45"})
        return httpx.Response(200, json=[{"symbol": "PEPEUSDT", "price": "0.0000125"}])

    async def check() -> None:
        nonlocal clock
        async with httpx.AsyncClient(base_url=market.BASE_URL, transport=httpx.MockTransport(reply)) as client:
            source = market.BinanceMarket(client)
            assert await source.ticker_prices() == {}
            assert await source.klines("PEPEUSDT") == ()
            clock += 44
            assert await source.ticker_prices() == {}
            assert len(calls) == 1
            clock += 1
            assert await source.ticker_prices() == {"PEPEUSDT": Decimal("0.0000125")}

    asyncio.run(check())
    assert calls == ["/fapi/v1/ticker/price"] * 2
