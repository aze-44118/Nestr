"""Modèles Pydantic pour l'API Nestr."""
from datetime import datetime
from typing import Dict, Literal, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Requête pour la génération de podcast."""
    user_id: UUID = Field(..., description="ID de l'utilisateur (requis)")
    user_token: Optional[str] = Field(None, description="Token d'authentification")
    intent: Literal["briefing", "wellness", "other"] = Field(..., description="Pipeline à utiliser directement (bypass détection)")
    message: str = Field(..., description="Message de l'utilisateur")
    lang: Literal["fr", "en"] = Field("fr", description="Langue du podcast")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "intent": "wellness",
                "message": "Peux-tu me créer un podcast sur la méditation matinale ?",
                "lang": "fr"
            }
        }


class IntentResult(BaseModel):
    """Résultat de la détection d'intention."""
    intent: Literal["briefing", "wellness", "other"]
    metadata: Dict[str, Any]
    messages: Dict[str, Dict[str, str]]


class EpisodeDTO(BaseModel):
    """DTO pour un épisode de podcast."""
    id: UUID
    user_id: UUID
    intent: str
    language: str
    title: str
    summary: str
    audio_path: str
    audio_url: str
    duration_sec: int
    published_at: datetime
    raw_meta: Dict[str, Any]


class GenerateResponse(BaseModel):
    """Réponse de la génération de podcast."""
    status: Literal["ok", "error"]
    rss_url: Optional[str] = Field(None, description="URL publique du flux RSS")
    message: str = Field(..., description="Message de succès ou d'erreur")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "rss_url": "https://example.supabase.co/storage/v1/object/public/podcasts/user123/rss.xml",
                "message": "Podcast généré avec succès !"
            }
        }


class HealthResponse(BaseModel):
    """Réponse du endpoint de santé."""
    ok: bool = True
