from decimal import Decimal
from pathlib import Path

from bot.models import AlertSpec
from bot.storage import AlertStorage


def test_price_rearm_keeps_cooldown_and_alert_id(tmp_path: Path) -> None:
    path = tmp_path / "alerts.sqlite3"
    storage = AlertStorage(path)
    storage.initialize()
    spec = AlertSpec("PEPEUSDT", "price", ">", Decimal("0.000012500"))

    alert_id, status = storage.add(100, spec, now=10)
    assert status == "added"
    assert storage.add(100, spec, now=11) == (alert_id, "existing")
    unchanged = storage.list_active()[0]
    assert storage.claim(unchanged, now=20, cooldown_seconds=900)
    assert not storage.claim(unchanged, now=20, cooldown_seconds=900)

    restarted = AlertStorage(path)
    restarted.initialize()
    [fired] = restarted.list_for_user(100)
    assert fired.spec.value == Decimal("0.0000125")
    assert fired.last_fired_at == 20 and not fired.active
    assert restarted.add(100, spec, now=25) == (alert_id, "rearmed")
    [rearmed] = restarted.list_active()
    assert not restarted.claim(rearmed, now=919, cooldown_seconds=900)
    assert restarted.claim(rearmed, now=920, cooldown_seconds=900)
    assert not restarted.list_active()


def test_recurring_alert_and_user_scoped_delete(tmp_path: Path) -> None:
    storage = AlertStorage(tmp_path / "alerts.sqlite3")
    storage.initialize()
    spec = AlertSpec("WIFUSDT", "volume", ">", Decimal(3))
    first, _ = storage.add(100, spec, now=10)
    second, _ = storage.add(200, spec, now=10)

    [alert] = storage.list_for_user(100)
    assert storage.claim(alert, now=20, cooldown_seconds=900)
    assert {entry.id for entry in storage.list_active()} == {first, second}
    assert not storage.delete(200, first)
    assert storage.delete(100, first)
    assert not storage.list_for_user(100)
    assert [entry.id for entry in storage.list_for_user(200)] == [second]
