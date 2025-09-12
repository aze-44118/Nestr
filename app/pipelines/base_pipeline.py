"""Pipeline de base pour la génération de podcasts."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime
import nanoid

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """Classe de base pour tous les pipelines de génération de podcasts."""
    
    def __init__(self, openai_manager, supabase_manager, rss_generator=None):
        """Initialise le pipeline avec les gestionnaires nécessaires."""
        self.openai = openai_manager
        self.supabase = supabase_manager
        self.rss_gen = rss_generator
    
    @abstractmethod
    def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère un podcast complet selon le type de pipeline.
        
        Args:
            user_id: ID de l'utilisateur
            message: Message original de l'utilisateur
            lang: Langue du podcast ("fr" ou "en")
            metadata: Métadonnées du podcast
            
        Returns:
            Dictionnaire avec les résultats de la génération
        """
        pass
    
    async def _generate_script(self, intent: str, metadata: Dict, message: str, lang: str, estimated_duration: int) -> str:
        """Génère le script via OpenAI."""
        logger.debug(f"_generate_script start intent={intent} est_dur={estimated_duration}")
        script = self.openai.generate_script(intent, metadata, message, lang, estimated_duration)
        logger.debug(f"_generate_script done len={len(script)}")
        return script
    
    async def _generate_audio(self, script: str) -> bytes:
        """Génère l'audio via OpenAI TTS."""
        logger.debug(f"_generate_audio start script_len={len(script)}")
        audio = self.openai.tts_to_bytes(script)
        logger.debug(f"_generate_audio done bytes={len(audio)}")
        return audio
    
    async def _upload_audio(self, user_id: str, audio_bytes: bytes) -> Tuple[str, str]:
        """Upload l'audio vers Supabase."""
        try:
            # Générer un nom de fichier unique
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}-{nanoid.generate()}.mp3"
            path = f"{user_id}/{filename}"
            
            # Upload vers Supabase
            audio_url = self.supabase.upload_public(
                path=path,
                data=audio_bytes,
                content_type="audio/mpeg"
            )
            
            return path, audio_url
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload audio: {e}")
            raise
    
    async def _save_episode(self, user_id: str, intent: str, lang: str, metadata: Dict, 
                     audio_path: str, audio_url: str, script: str, audio_bytes: bytes) -> Dict[str, Any]:
        """Sauvegarde l'épisode en base de données."""
        from ..utils import format_datetime
        
        # Calculer la durée réelle du fichier audio
        real_duration_sec = self._calculate_audio_duration(audio_bytes)
        
        episode_data = {
            "user_id": user_id,
            "intent": intent,
            "language": lang,
            "title": metadata.get("episode_title", "Podcast généré"),
            "summary": metadata.get("episode_summary", "Podcast généré automatiquement"),
            "audio_path": audio_path,
            "audio_url": audio_url,
            "duration_sec": real_duration_sec,
            "published_at": format_datetime(),  # Pas d'argument !
            "raw_meta": metadata
        }
        
        try:
            logger.info(f"Sauvegarde épisode: {episode_data['title']}")
            result = self.supabase.insert_episode(episode_data)
            logger.info(f"✅ Épisode sauvegardé: {result['id']}")
            return result
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion de l'épisode: {e}")
            raise
    
    def _calculate_audio_duration(self, audio_bytes: bytes) -> int:
        """Calcule la durée réelle d'un fichier audio (MP3 ou WAV)."""
        try:
            from mutagen.mp3 import MP3
            from mutagen.wave import WAVE
            import io
            
            # Essayer MP3 d'abord
            try:
                audio_file = io.BytesIO(audio_bytes)
                mp3 = MP3(audio_file)
                duration_sec = int(mp3.info.length)
                logger.info(f"Durée audio MP3 calculée: {duration_sec}s")
                return duration_sec
            except:
                # Essayer WAV
                try:
                    audio_file = io.BytesIO(audio_bytes)
                    wav = WAVE(audio_file)
                    duration_sec = int(wav.info.length)
                    logger.info(f"Durée audio WAV calculée: {duration_sec}s")
                    return duration_sec
                except:
                    # Fallback: estimation basique
                    # WAV 22kHz: 22050 * 2 bytes * 1 channel = 44100 bytes/sec
                    # WAV 44.1kHz: 44100 * 2 bytes * 1 channel = 88200 bytes/sec
                    # MP3: estimation ~16KB/sec
                    estimated_duration = len(audio_bytes) // 44100  # WAV 22kHz estimation
                    if estimated_duration < 1:
                        estimated_duration = len(audio_bytes) // 16000  # MP3 estimation
                    logger.warning(f"Estimation durée audio: {estimated_duration}s")
                    return max(1, estimated_duration)
            
        except Exception as e:
            logger.warning(f"Impossible de calculer la durée audio: {e}")
            # Estimation basique : 1 seconde pour 16KB
            return max(1, len(audio_bytes) // 16000)
    
    async def _regenerate_rss(self, user_id: str) -> str:
        """Régénère le flux RSS pour l'utilisateur."""
        if not self.rss_gen:
            logger.warning("RSSGenerator non disponible, génération RSS ignorée")
            return "RSS non généré"
        
        from ..utils import make_rss_path
        
        # Récupérer les épisodes de l'utilisateur
        logger.info(f"📡 Régénération RSS pour {user_id}")
        episodes = self.supabase.list_episodes(user_id)
        
        if not episodes:
            logger.warning(f"Aucun épisode trouvé pour {user_id}")
            # Créer un RSS vide mais valide
            episodes = []
        
        # Générer le RSS
        logger.info(f"📡 Génération RSS avec {len(episodes)} épisodes")
        from ..config import settings
        rss_xml = self.rss_gen.build_rss_xml(
            user_id=user_id,
            lang=settings.rss_language,
            episodes=episodes,
            feed_meta={
                "feed_title": settings.rss_feed_title.format(user_id=user_id),
                "feed_description": settings.rss_feed_description.format(user_id=user_id),
                "feed_author": settings.rss_author,
                "language": settings.rss_language,
                "category": settings.rss_category,
                "cover_url": settings.rss_cover_url,
                "site_url": settings.rss_site_url,
                "ttl": settings.rss_ttl_minutes,
            }
        )
        
        # Upload du RSS
        rss_path = make_rss_path(user_id)
        logger.info(f" Upload RSS vers {rss_path}")
        return self.supabase.upload_rss(user_id, rss_xml)
