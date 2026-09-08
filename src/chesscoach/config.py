"""Optional service settings; configuration is read only on explicit request."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """A service is not configured; suitable for a user-facing message."""


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = field(default="", repr=False)
    openai_model: str = ""
    stockfish_path: str = ""

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "Settings":
        """Optionally load an explicit .env; existing environment values win."""
        if env_file is not None:
            load_dotenv(env_file, override=False)
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            stockfish_path=os.getenv("STOCKFISH_PATH", "").strip(),
        )

    def require_ai(self) -> None:
        if not self.openai_api_key:
            raise ConfigurationError(
                "AI coaching is not configured. Set OPENAI_API_KEY locally to enable it later. "
                "Local chess does not need an API key."
            )
        if not self.openai_model:
            raise ConfigurationError("Set OPENAI_MODEL before requesting AI coaching.")
