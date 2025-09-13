"""Nestr application configuration."""
import os
from typing import Literal, Optional

from pydantic_settings import BaseSettings
from pydantic import Field
from .prompts import load_prompt


class Settings(BaseSettings):
    """Application configuration with environment variable validation."""
    
    # OpenAI
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Supabase
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str = Field(..., env="SUPABASE_ANON_KEY")
    supabase_podcast_bucket: str = Field(default="podcasts", env="SUPABASE_PODCAST_BUCKET")
    
    # TTS
    default_tts_model: str = Field(default="gpt-4o-mini-tts", env="DEFAULT_TTS_MODEL")
    default_tts_voice: str = Field(default="alloy", env="DEFAULT_TTS_VOICE")
    default_lang: Literal["fr", "en"] = Field(default="fr", env="DEFAULT_LANG")
    
    # App
    app_name: str = "Nestr API"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    environment: Literal["development", "production"] = Field(default="development", env="ENVIRONMENT")
    reload: bool = Field(default=True, env="RELOAD")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="detailed", env="LOG_FORMAT")  # simple, detailed, json

    # RSS (centralized parameters)
    rss_feed_title: str = Field(default="Nestr – {user_id}", env="RSS_FEED_TITLE")
    rss_feed_description: str = Field(default="Personalized podcasts for {user_id}", env="RSS_FEED_DESCRIPTION")
    rss_author: str = Field(default="Nestr", env="RSS_AUTHOR")
    rss_language: Literal["fr", "en"] = Field(default="fr", env="RSS_LANGUAGE")
    rss_category: str = Field(default="Education", env="RSS_CATEGORY")
    rss_cover_url: str = Field(default="", env="RSS_COVER_URL")
    rss_site_url: str = Field(default="https://nestr.app", env="RSS_SITE_URL")
    rss_ttl_minutes: int = Field(default=60, env="RSS_TTL_MINUTES")

    # Generation (centralized)
    gen_default_model: str = Field(default="gpt-4o-mini", env="GEN_DEFAULT_MODEL")
    gen_default_lang: Literal["fr", "en"] = Field(default="fr", env="GEN_DEFAULT_LANG")

    # TTS (centralized) for 'other' (dialogue)
    # Nestr presenter (male) = speaker_1
    tts_model_other: str = Field(default="gpt-4o-mini-tts", env="TTS_MODEL_OTHER")
    tts_voice_other_speaker_1: str = Field(default="alloy", env="TTS_VOICE_OTHER_SPK1")
    # Co-host (female) = speaker_2
    tts_voice_other_speaker_2: str = Field(default="onyx", env="TTS_VOICE_OTHER_SPK2")

    # TTS prompt names in prompts_tts.json
    tts_prompt_other_speaker_1: str = Field(default="other_tts_speaker_1", env="TTS_PROMPT_OTHER_SPK1")
    tts_prompt_other_speaker_2: str = Field(default="other_tts_speaker_2", env="TTS_PROMPT_OTHER_SPK2")
    
    # Telegram (optional to allow startup without variables)
    telegram_token: Optional[str] = Field(default=None, env="TELEGRAM_TOKEN")
    telegram_service_id: Optional[str] = Field(default=None, env="TELEGRAM_SERVICE_ID")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore additional variables


# Global settings instance
settings = Settings()

# Log configuration
LOG_COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "CRITICAL": "\033[35m", # Magenta
    "RESET": "\033[0m"      # Reset
}


# Function to load prompts from files
def get_prompt(prompt_name: str) -> str:
    """Retrieve a prompt by name from text files."""
    return load_prompt(prompt_name)
