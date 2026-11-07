from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_cloud_project: str | None = None
    google_cloud_account: str | None = None
    epo_ops_key: str | None = None
    epo_ops_secret: str | None = None
    uspto_odp_api_key: str | None = None
    llm_model: str | None = None
    census_api_key: str | None = None
    patentic_cache_dir: Path = Path(".cache")
    patentic_outputs_dir: Path = Path("outputs")
