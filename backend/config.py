"""Central configuration, loaded once from the environment / .env.

Everything that touches a secret or a tunable reads from here so that the rest
of the codebase never sees `os.environ` directly and never hardcodes a key.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root is one level up from backend/. Keeps the SQLite file and seed
# assets resolvable no matter which directory uvicorn is launched from.
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
SEED_DIR = BACKEND_DIR / "seed"


class Settings(BaseSettings):
    # Loads the repo-root .env; unknown keys are ignored so the file can hold
    # extra notes without breaking startup.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Gemini (AI Studio key, NOT Vertex) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_max_retries: int = 5
    gemini_base_delay: float = 1.0

    # --- Slack (optional; comms falls back to console when empty) ---
    slack_webhook_url: str = ""

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8080

    # --- Storage ---
    aegis_db_path: str = "aegisops.db"

    @property
    def db_path(self) -> Path:
        """Absolute DB path so state is stable regardless of launch cwd."""
        p = Path(self.aegis_db_path)
        return p if p.is_absolute() else (REPO_ROOT / p)

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key and "paste_your" not in self.gemini_api_key)

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_webhook_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
