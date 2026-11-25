from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


MINUTE_MS = 60_000
AlertKind = Literal["price", "volume", "move"]
Operator = Literal[">", "<"]


@dataclass(frozen=True, slots=True)
class AlertSpec:
    symbol: str
    kind: AlertKind
    op: Operator
    value: Decimal


@dataclass(frozen=True, slots=True)
class Alert:
    id: int
    user_id: int
    spec: AlertSpec
    active: bool
    last_fired_at: int | None
    created_at: int


@dataclass(frozen=True, slots=True)
class Candle:
    open_time_ms: int
    close: Decimal
    volume: Decimal


def decimal_text(value: Decimal) -> str:
    """Use the same exact decimal representation in SQLite and messages."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
