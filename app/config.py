"""Configuration management for Nestr application."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App configuration
    app_name: str = "Nestr"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "production"
    log_format: str = "simple"
    
    # OpenAI configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    openai_voice: str = "alloy"
    
    # Supabase configuration
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_podcast_bucket: str = "podcasts"
    
    # Telegram configuration
    telegram_token: Optional[str] = None
    telegram_service_id: Optional[str] = None
    
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    reload: bool = False
    
    # TTS Configuration
    default_tts_model: str = "gpt-4o-mini-tts"
    default_tts_voice: str = "alloy"
    default_lang: str = "fr"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings()

# Log colors for terminal output
LOG_COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "CRITICAL": "\033[35m", # Magenta
    "RESET": "\033[0m"      # Reset
}
