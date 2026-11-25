from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .models import MINUTE_MS, AlertSpec, Candle


WINDOW_MINUTES = 5
BASELINE_MINUTES = 120
CANDLE_LIMIT = BASELINE_MINUTES + WINDOW_MINUTES


@dataclass(frozen=True, slots=True)
class CandleMetrics:
    change_percent: Decimal | None
    volume_multiple: Decimal | None


def _continuous_window(candles: Sequence[Candle], size: int) -> Sequence[Candle]:
    window = candles[-size:]
    if len(window) != size or any(
        right.open_time_ms - left.open_time_ms != MINUTE_MS
        for left, right in zip(window, window[1:])
    ):
        return ()
    return window


def candle_metrics(candles: Sequence[Candle]) -> CandleMetrics:
    """Compute indicators from chronological, closed one-minute candles."""
    change = None
    movement = _continuous_window(candles, WINDOW_MINUTES + 1)
    if movement and movement[0].close > 0:
        change = (movement[-1].close - movement[0].close) * 100 / movement[0].close

    multiple = None
    history = _continuous_window(candles, CANDLE_LIMIT)
    if history:
        average = sum(candle.volume for candle in history[:BASELINE_MINUTES]) / (
            BASELINE_MINUTES // WINDOW_MINUTES
        )
        if average > 0:
            recent = sum(candle.volume for candle in history[BASELINE_MINUTES:])
            multiple = recent / average

    return CandleMetrics(change, multiple)


def condition_met(
    spec: AlertSpec, price: Decimal, metrics: CandleMetrics | None = None
) -> bool:
    if spec.kind == "price":
        return price > spec.value if spec.op == ">" else price < spec.value
    if metrics is None:
        return False
    if spec.kind == "volume":
        return metrics.volume_multiple is not None and metrics.volume_multiple > spec.value
    return metrics.change_percent is not None and abs(metrics.change_percent) > spec.value


def cooldown_ready(last_fired_at: int | None, now: int, cooldown_seconds: int) -> bool:
    return last_fired_at is None or now - last_fired_at >= cooldown_seconds
