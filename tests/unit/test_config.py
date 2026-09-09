from pathlib import Path
from unittest.mock import patch

import pytest

from chesscoach.ai.client import create_client
from chesscoach.config import (
    ConfigurationError,
    Settings,
    apply_process_settings,
    save_local_settings,
)


def test_no_credentials_required_to_read_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "STOCKFISH_PATH"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_environment()
    assert settings == Settings()
    with pytest.raises(ConfigurationError, match="Local chess does not need an API key"):
        create_client(settings)


def test_model_required() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_MODEL"):
        create_client(Settings(openai_api_key="test-only"))


def test_environment_precedes_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_MODEL=file-model\nSTOCKFISH_PATH=local-engine\n")
    monkeypatch.setenv("OPENAI_API_KEY", " test-only ")
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")
    monkeypatch.delenv("STOCKFISH_PATH", raising=False)
    settings = Settings.from_environment(env_file)
    assert settings.openai_api_key == "test-only"
    assert settings.openai_model == "environment-model"
    assert settings.stockfish_path == "local-engine"
    assert "test-only" not in repr(settings)


def test_sdk_construction_is_explicit() -> None:
    with patch("openai.OpenAI") as sdk:
        client = create_client(Settings(openai_api_key="test-only", openai_model="test-model"))
        sdk.assert_called_once_with(api_key="test-only")
        assert client is sdk.return_value
        assert client.mock_calls == []


def test_local_settings_update_preserves_unrelated_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=value\nOPENAI_API_KEY=old\nOPENAI_MODEL=old-model\n")
    save_local_settings(
        env_file,
        {"OPENAI_API_KEY": "new-secret", "OPENAI_MODEL": "model", "STOCKFISH_PATH": ""},
    )
    assert env_file.read_text() == "OTHER=value\nOPENAI_API_KEY=new-secret\nOPENAI_MODEL=model\n"


def test_apply_process_settings_updates_and_removes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STOCKFISH_PATH", "old")
    apply_process_settings(Settings(openai_api_key="key", openai_model="model"))
    assert Settings.from_environment() == Settings(openai_api_key="key", openai_model="model")


def test_local_settings_reject_line_breaks(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="line breaks"):
        save_local_settings(tmp_path / ".env", {"OPENAI_API_KEY": "secret\nBAD=value"})
