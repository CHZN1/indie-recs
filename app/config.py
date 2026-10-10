from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal['development', 'production'] = 'development'
    auth_required: bool = False
    background_training: bool = False
    max_upload_bytes: int = 5_000_000

    @model_validator(mode='after')
    def production_guard(self):
        if self.environment == 'production' and (not self.auth_required or not self.background_training):
            raise ValueError('Production requires AUTH_REQUIRED=true and BACKGROUND_TRAINING=true')
        if self.max_upload_bytes < 1:
            raise ValueError('MAX_UPLOAD_BYTES must be positive')
        return self

    tmdb_api_key: str = ""
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'indie_recs.db'}"
    model_path: str = str(ROOT_DIR / "models" / "svd_model.joblib")
    tmdb_cache_ttl_days: int = 30
    tmdb_base_url: str = "https://api.themoviedb.org/3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
