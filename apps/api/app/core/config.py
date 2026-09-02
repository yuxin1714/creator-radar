from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Creator Radar API"
    database_url: str = "postgresql+psycopg://creator_radar:local_only_change_me@127.0.0.1:5432/creator_radar"
    redis_url: str = "redis://127.0.0.1:6379/0"
    metadata_provider: str = "tikhub"
    tikhub_api_key: str = ""
    tikhub_base_url: str = "https://api.tikhub.io"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    asr_provider: str = ""
    asr_api_key: str = ""
    asr_model_path: str = "F:/DevTools/AI/whisper-models/large-v3-turbo"
    asr_device: str = "cuda"
    asr_compute_type: str = "int8_float16"
    media_cache_dir: str = "F:/DevTools/AI/media-cache"
    media_max_bytes: int = 500_000_000
