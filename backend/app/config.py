"""Configuração central carregada de variáveis de ambiente / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        self.gmail_user: str = os.getenv("GMAIL_USER", "").strip()
        self.gmail_app_password: str = os.getenv("GMAIL_APP_PASSWORD", "").strip()
        self.default_recipient: str = os.getenv("DEFAULT_RECIPIENT", "").strip()

        raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        self.cors_origins: list[str] = [o.strip() for o in raw_origins.split(",") if o.strip()]

        data_dir_raw = os.getenv("DATA_DIR", "data")
        data_path = Path(data_dir_raw)
        self.data_dir: Path = data_path if data_path.is_absolute() else (BACKEND_DIR / data_path)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def email_configured(self) -> bool:
        return bool(self.gmail_user and self.gmail_app_password)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
