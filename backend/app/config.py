"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Every value can be overridden via .env."""

    model_config = SettingsConfigDict(
        env_file=(str(ROOT / ".env"), ".env"), extra="ignore"
    )

    image_model_id: str = "umm-maybe/AI-image-detector"
    audio_model_id: str = "mo-thecreator/Deepfake-audio-detection"
    device: str = "auto"  # auto | cpu | cuda

    llm_provider: str = "none"  # anthropic | openai | gemini | ollama | none
    llm_model: str = ""
    llm_api_key: str = ""
    ollama_url: str = "http://localhost:11434"
    llm_timeout_s: float = 12.0
    llm_send_text: bool = True  # allow sending message text to the configured LLM for classification
    preload_models: bool = True

    max_image_mb: int = 10
    max_audio_mb: int = 15
    max_text_chars: int = 5000
    max_audio_seconds: int = 60

    risk_low_max: int = 35
    risk_high_min: int = 65

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_list(self) -> list[str]:
        """CORS origins as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings object."""
    return Settings()
