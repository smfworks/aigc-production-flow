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
    celery_broker_url: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_client_id: str = ""
    oidc_jwks_url: str = ""
    oidc_name_claim: str = "preferred_username"
    oidc_role_claim: str = ""
    oidc_role_map: str = ""
    oidc_apply_role_claim: bool = False
    still_adapter: str = "stub"
    clip_adapter: str = "stub"
    adapter_webhook_url: str = ""
    adapter_cli: str = ""
    adapter_timeout_seconds: float = 60.0
    # Native ComfyUI lanes. Empty means the comfy-* slot stays not-live (stub),
    # unless a webhook or CLI hook is set. Defaults are overridable checkpoint names.
    comfy_still_lanes: str = ""
    comfy_clip_lanes: str = ""
    comfy_image_lanes_for_free: str = ""
    comfy_allow_hosts: str = ""
    comfy_out_dir: str = ""
    comfy_request_timeout_seconds: float = 30.0
    comfy_still_timeout_seconds: float = 300.0
    comfy_still_poll_seconds: float = 4.0
    comfy_poll_interval_seconds: float = 15.0
    comfy_qwen_unet: str = "qwen_image_2.1_int8_convrot.safetensors"
    comfy_qwen_clip: str = "qwen3vl_8b_int8_convrot.safetensors"
    comfy_qwen_vae: str = "qwen_image_2.1_vae_bf16.safetensors"
    comfy_h3_unet_full: str = "minimax_h3_ref2va_pruned_int8_convrot.safetensors"
    comfy_h3_unet_turbo: str = "minimax_h3_ref2va_pruned_turbo_int8_convrot.safetensors"
    comfy_h3_clip: str = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    comfy_h3_video_vae: str = "minimax_h3_video_vae_fp16.safetensors"
    comfy_h3_audio_vae: str = "minimax_h3_audio_vae_fp32.safetensors"
    comfy_h3_styles: str = ""
    comfy_h3_max_frames: int = 362
    comfy_h3_fps: float = 24.0
    comfy_h3_width: int = 960
    comfy_h3_height: int = 544
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
    notify_webhook_url: str = ""
    # Optional local/OpenAI-compatible chat endpoint for brain-dump drafts.
    # Unset means deterministic template expansion. Never claim a model ran.
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    # Hermes brief drop. Empty uses <media parent>/handoff (./data/handoff next to ./data/media).
    handoff_root: str = ""
    # Optional second copy, for example ~/.hermes/aigc. Empty does not write outside the handoff root.
    hermes_drop: str = ""
    # Local Create recipes. Empty uses <media parent>/recipes (./data/recipes next to ./data/media).
    recipe_root: str = ""

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
