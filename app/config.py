from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tmdb_api_key: str = ""
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'indie_recs.db'}"
    model_path: str = str(ROOT_DIR / "models" / "svd_model.joblib")
    tmdb_cache_ttl_days: int = 30
    tmdb_base_url: str = "https://api.themoviedb.org/3"


@lru_cache
def get_settings() -> Settings:
    return Settings()
