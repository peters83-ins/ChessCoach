from pathlib import Path
from unittest.mock import patch

import pytest

from chesscoach.ai.client import create_client
from chesscoach.config import ConfigurationError, Settings


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
