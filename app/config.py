from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # absolute path: works no matter which folder you launch uvicorn/scripts from
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parent.parent / ".env", extra="ignore")

    database_url: str = ""
    jwt_secret: str = ""
    api_key_secret: str = ""  # derives revealable API keys; falls back to JWT_SECRET. Never change it once keys exist.
    internal_tick_secret: str = ""
    app_base_url: str = "http://localhost:8000"      # public URL of this API (used for webhook URL docs)
    pay_gate_url: str = ""  # empty = use the pay page this server serves itself ({APP_BASE_URL}/pay/<id>)
    cors_origins: str = "*"                          # comma separated, "*" = any
    allow_signup: bool = True
    # DEV ONLY: lets TEST-mode webhook/redirect URLs point at localhost so scripts can receive webhooks.
    # Never enable in production (it relaxes the SSRF guard, for test mode only).
    allow_private_webhook_urls: bool = False

    # LIVE mode = real money through Campay production
    campay_live_username: str = ""
    campay_live_password: str = ""
    campay_live_webhook_key: str = ""
    campay_live_base_url: str = "https://campay.net/api/"

    # TEST mode = "simulated" (built-in fake provider, no external calls) or "campay_demo"
    test_provider: str = "simulated"
    campay_demo_username: str = ""
    campay_demo_password: str = ""
    campay_demo_webhook_key: str = ""
    campay_demo_base_url: str = "https://demo.campay.net/api/"

    @property
    def gate_url(self) -> str:
        return (self.pay_gate_url or f"{self.app_base_url.rstrip('/')}/pay").rstrip("/")

    @property
    def key_secret(self) -> str:
        return self.api_key_secret or self.jwt_secret

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
