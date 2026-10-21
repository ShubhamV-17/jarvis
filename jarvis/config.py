"""Application configuration loaded from environment variables and .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    log_level: str
    model: str
    openai_api_key: str | None = field(default=None, repr=False)

    @property
    def database_file(self) -> Path:
        return self.data_dir / "jarvis.sqlite3"

    @property
    def log_file(self) -> Path:
        return self.project_root / "logs" / "jarvis.log"


def load_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or PROJECT_ROOT).resolve()
    load_dotenv(root / ".env")

    log_level = os.getenv("JARVIS_LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Unsupported JARVIS_LOG_LEVEL: {log_level}")

    configured_data_dir = Path(os.getenv("JARVIS_DATA_DIR", "data"))
    data_dir = configured_data_dir if configured_data_dir.is_absolute() else root / configured_data_dir

    model = os.getenv("JARVIS_MODEL", "gpt-5-mini").strip()
    if not model:
        raise ValueError("JARVIS_MODEL must not be empty")

    api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
    return Settings(
        project_root=root,
        data_dir=data_dir.resolve(),
        log_level=log_level,
        model=model,
        openai_api_key=api_key,
    )
