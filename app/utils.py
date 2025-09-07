"""Utilitaires pour l'application Nestr."""
import hashlib
from datetime import datetime, timezone
from typing import Optional

from nanoid import generate


def nanoid(length: int = 10) -> str:
    """Génère un ID unique aléatoire."""
    return generate(size=length)


def now_utc_rfc822() -> str:
    """Retourne la date/heure actuelle au format RFC822 (UTC)."""
    now = datetime.now(timezone.utc)
    return now.strftime("%a, %d %b %Y %H:%M:%S %z")


def format_datetime() -> str:
    """Retourne la date/heure actuelle au format ISO (UTC)."""
    now = datetime.now(timezone.utc)
    return now.isoformat()


def safe_filename(text: str, max_length: int = 50) -> str:
    """Crée un nom de fichier sûr à partir d'un texte."""
    # Remplacer les caractères non sécurisés
    safe = "".join(c for c in text.lower() if c.isalnum() or c in " -_")
    safe = safe.replace(" ", "-").replace("_", "-")
    
    # Limiter la longueur
    if len(safe) > max_length:
        safe = safe[:max_length]
    
    # Supprimer les tirets multiples
    while "--" in safe:
        safe = safe.replace("--", "-")
    
    # Supprimer les tirets en début/fin
    safe = safe.strip("-")
    
    return safe or "file"


def make_audio_path(user_id: str, timestamp: Optional[datetime] = None) -> str:
    """Génère un chemin d'audio non devinable."""
    if timestamp is None:
        timestamp = datetime.now()
    
    # Format: YYYYMMDD-HHMMSS-nanoid.mp3
    date_str = timestamp.strftime("%Y%m%d-%H%M%S")
    unique_id = nanoid(8)
    
    return f"{user_id}/{date_str}-{unique_id}.mp3"


def make_rss_path(user_id: str) -> str:
    """Génère le chemin du fichier RSS pour un utilisateur."""
    return f"{user_id}/rss.xml"


def hash_string(text: str) -> str:
    """Hash un texte avec SHA-256."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def format_duration(seconds: int) -> str:
    """Formate une durée en secondes en format lisible."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m{remaining_seconds}s" if remaining_seconds > 0 else f"{minutes}m"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        return f"{hours}h{remaining_minutes}m"


def default_metadata_for_generation(message: str = "") -> dict:
    """Métadonnées par défaut pour la génération (bypass intent)."""
    # Générer un titre basé sur le message si fourni
    title = "Podcast Nestr"
    if message:
        # Prendre les premiers mots du message comme titre
        words = message.split()[:6]  # Max 6 mots
        title = " ".join(words)
        if len(title) > 50:
            title = title[:47] + "..."
    
    return {
        "episode_title": title,
        "episode_summary": f"Podcast généré automatiquement sur le thème : {message[:100]}" if message else "Podcast généré automatiquement",
        "estimated_duration_sec": 180,
        "messages": {
            "success": {"fr": "Podcast généré", "en": "Podcast generated"},
            "error": {"fr": "Erreur lors de la génération", "en": "Generation error"}
        }
    }
