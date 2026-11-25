import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .models import Alert, AlertSpec, decimal_text


AddStatus = Literal["added", "existing", "rearmed"]


class AlertStorage:
    """Short SQLite transactions, safe to call from a worker thread."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            yield db

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('price', 'volume', 'move')),
                    op TEXT NOT NULL CHECK (op IN ('>', '<')),
                    value TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    last_fired_at INTEGER,
                    created_at INTEGER NOT NULL,
                    UNIQUE (user_id, symbol, kind, op, value)
                );

                CREATE INDEX IF NOT EXISTS alerts_active ON alerts(id) WHERE active = 1;
                """
            )

    def add(self, user_id: int, spec: AlertSpec, now: int) -> tuple[int, AddStatus]:
        key = (user_id, spec.symbol, spec.kind, spec.op, decimal_text(spec.value))
        with self._connect() as db:
            inserted = db.execute(
                """
                INSERT INTO alerts (user_id, symbol, kind, op, value, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (user_id, symbol, kind, op, value) DO NOTHING
                """,
                (*key, now),
            )
            if inserted.rowcount and inserted.lastrowid is not None:
                return inserted.lastrowid, "added"

            row = db.execute(
                """
                SELECT id, active FROM alerts
                WHERE user_id = ? AND symbol = ? AND kind = ? AND op = ? AND value = ?
                """,
                key,
            ).fetchone()
            if row is None:
                raise RuntimeError("Не удалось найти сохранённый алерт.")
            alert_id: int = row["id"]
            if row["active"]:
                return alert_id, "existing"

            db.execute("UPDATE alerts SET active = 1 WHERE id = ?", (alert_id,))
            return alert_id, "rearmed"

    def list_for_user(self, user_id: int) -> list[Alert]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM alerts WHERE user_id = ? ORDER BY id", (user_id,))
            return [self._to_alert(row) for row in rows]

    def list_active(self) -> list[Alert]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM alerts WHERE active = 1 ORDER BY id")
            return [self._to_alert(row) for row in rows]

    def delete(self, user_id: int, alert_id: int) -> bool:
        with self._connect() as db:
            result = db.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))
            return result.rowcount == 1

    def claim(self, alert: Alert, now: int, cooldown_seconds: int) -> bool:
        """Record an attempt before sending, including across process restarts."""
        with self._connect() as db:
            result = db.execute(
                """
                UPDATE alerts
                SET last_fired_at = ?, active = CASE WHEN kind = 'price' THEN 0 ELSE 1 END
                WHERE id = ? AND active = 1 AND last_fired_at IS ?
                  AND (last_fired_at IS NULL OR last_fired_at <= ?)
                """,
                (now, alert.id, alert.last_fired_at, now - cooldown_seconds),
            )
            return result.rowcount == 1

    def rearm_after_send_error(self, alert_id: int, attempted_at: int) -> None:
        with self._connect() as db:
            db.execute(
                """
                UPDATE alerts SET active = 1
                WHERE id = ? AND kind = 'price' AND last_fired_at = ?
                """,
                (alert_id, attempted_at),
            )

    @staticmethod
    def _to_alert(row: sqlite3.Row) -> Alert:
        return Alert(
            id=row["id"],
            user_id=row["user_id"],
            spec=AlertSpec(row["symbol"], row["kind"], row["op"], Decimal(row["value"])),
            active=bool(row["active"]),
            last_fired_at=row["last_fired_at"],
            created_at=row["created_at"],
        )
