"""Optional service settings; configuration is read only on explicit request."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile

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


def save_local_settings(path: Path, updates: dict[str, str]) -> None:
    """Update selected values in a local dotenv file without exposing secrets."""
    allowed = {"OPENAI_API_KEY", "OPENAI_MODEL", "STOCKFISH_PATH"}
    if not updates.keys() <= allowed:
        raise ValueError("Unsupported setting name.")
    if any("\n" in value or "\r" in value for value in updates.values()):
        raise ValueError("Settings cannot contain line breaks.")
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in existing:
        name = line.split("=", 1)[0].strip() if "=" in line else ""
        if name in remaining:
            value = remaining.pop(name)
            if value:
                output.append(f"{name}={value}")
            continue
        output.append(line)
    output.extend(f"{name}={value}" for name, value in remaining.items() if value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as temporary:
        temporary.write("\n".join(output).rstrip() + "\n")
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def apply_process_settings(settings: Settings) -> None:
    """Apply settings to this process so the UI does not need a restart."""
    values = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_MODEL": settings.openai_model,
        "STOCKFISH_PATH": settings.stockfish_path,
    }
    for name, value in values.items():
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
