import pytest

pytest.importorskip("aiogram")

from bot.handlers import build_router  # noqa: E402
from bot.main import Settings  # noqa: E402


def test_router_registers_commands() -> None:
    assert len(build_router().message.handlers) == 4


def test_settings_require_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "")
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        Settings.from_env()
