"""Pydantic models for Nestr application."""
from typing import Optional, Dict, Any
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""
    ok: bool


class TelegramUser(BaseModel):
    """Telegram user model."""
    id: int
    is_bot: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat model."""
    id: int
    type: str


class TelegramMessage(BaseModel):
    """Telegram message model."""
    message_id: int
    from_user: TelegramUser
    chat: TelegramChat
    text: Optional[str] = None


class TelegramWebhookRequest(BaseModel):
    """Telegram webhook request model."""
    update_id: int
    message: Optional[TelegramMessage] = None


class PodcastGenerationRequest(BaseModel):
    """Podcast generation request model."""
    message: str
    intent: str = "other"
    lang: str = "fr"
    metadata: Optional[Dict[str, Any]] = None


class PodcastGenerationResponse(BaseModel):
    """Podcast generation response model."""
    status: str
    message: str
    episode_title: Optional[str] = None
    duration_sec: Optional[int] = None
    rss_url: Optional[str] = None
    audio_url: Optional[str] = None
