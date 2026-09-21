from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STUDIO_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/studio.db"
    media_root: str = "./data/media"
    api_token: str = "local-dev-token"
    default_user: str = "local-dev"
    default_org_name: str = "SMF Works (local)"
    pack_builder_url: str = "http://localhost:5173"
    cors_origins: str = (
        "http://localhost:5173,http://localhost:5174,"
        "http://127.0.0.1:5173,http://127.0.0.1:5174"
    )
    job_worker: str = "thread"
    job_poll_seconds: float = 0.25
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    adapter_webhook_url: str = ""
    adapter_cli: str = ""
    adapter_timeout_seconds: float = 60.0
    auth_mode: str = "local"
    cost_rates: str = "stub:0.1,webhook:1,cli:1,comfy-h3:2,comfy-qwen:0.5"
    cost_currency: str = "credits"
    cost_usd_per_unit: float = 0.0
    budget_cap_units: float | None = None
    budget_hard_stop: bool = False
    retention_days: int = 30
    templates_root: str = ""
    media_backend: str = "local"
    s3_bucket: str = ""
    s3_endpoint: str = ""
    s3_prefix: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    presence_ttl_seconds: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def media_path(self) -> Path:
        path = Path(self.media_root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url.startswith("sqlite:///"):
        raw = settings.database_url.removeprefix("sqlite:///")
        if raw not in {":memory:", ""} and not raw.startswith("/"):
            Path(raw).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return settings
