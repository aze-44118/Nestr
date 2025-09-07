"""Configuration de l'application Nestr."""
import os
from typing import Literal

from pydantic_settings import BaseSettings
from pydantic import Field
from .prompts import load_prompt


class Settings(BaseSettings):
    """Configuration de l'application avec validation des variables d'environnement."""
    
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
    app_name: str = "Nestr Noesis API"
    app_version: str = "0.1.0"
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

    # RSS (paramètres centralisés)
    rss_feed_title: str = Field(default="Nestr – {user_id}", env="RSS_FEED_TITLE")
    rss_feed_description: str = Field(default="Podcasts personnalisés de {user_id}", env="RSS_FEED_DESCRIPTION")
    rss_author: str = Field(default="Nestr", env="RSS_AUTHOR")
    rss_language: Literal["fr", "en"] = Field(default="fr", env="RSS_LANGUAGE")
    rss_category: str = Field(default="Education", env="RSS_CATEGORY")
    rss_cover_url: str = Field(default="", env="RSS_COVER_URL")
    rss_site_url: str = Field(default="https://nest.noesis.app", env="RSS_SITE_URL")
    rss_ttl_minutes: int = Field(default=60, env="RSS_TTL_MINUTES")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignorer les variables supplémentaires


# Instance globale des paramètres
settings = Settings()

# Configuration des logs
LOG_COLORS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Vert
    "WARNING": "\033[33m",  # Jaune
    "ERROR": "\033[31m",    # Rouge
    "CRITICAL": "\033[35m", # Magenta
    "RESET": "\033[0m"      # Reset
}


# Fonction pour charger les prompts depuis les fichiers
def get_prompt(prompt_name: str) -> str:
    """Récupère un prompt par son nom depuis les fichiers texte."""
    return load_prompt(prompt_name)
