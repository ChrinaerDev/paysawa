from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent / ".env", extra="ignore")

    paysawa_base_url: str = "http://localhost:8000/api/"
    paysawa_username: str = ""
    paysawa_password: str = ""
    paysawa_webhook_key: str = ""
    port: int = 9000
    public_url: str = "http://localhost:9000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
