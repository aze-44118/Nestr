"""Pipeline de génération de podcasts de type briefing."""

import logging
from typing import Dict, Any

from .base_pipeline import BasePipeline

logger = logging.getLogger(__name__)


class BriefingPipeline(BasePipeline):
    """Pipeline spécialisé pour les podcasts de type briefing/informationnel."""
    
    async def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère un podcast de type briefing.
        
        Caractéristiques :
        - Ton informatif et engageant
        - Structure claire et concise
        - Focus sur l'actualité et les informations
        """
        try:
            logger.info(f"Génération podcast briefing pour user {user_id}")
            
            # 1. Génération du script
            script = await self._generate_script(
                intent="briefing",
                metadata=metadata,
                message=message,
                lang=lang,
                estimated_duration=metadata.get("estimated_duration_sec", 180)
            )
            
            # 2. Génération de l'audio
            audio_bytes = await self._generate_audio(script)
            
            # 3. Upload de l'audio
            audio_path, audio_url = await self._upload_audio(user_id, audio_bytes)
            
            # 4. Sauvegarde de l'épisode
            episode = await self._save_episode(
                user_id=user_id,
                intent="briefing",
                lang=lang,
                metadata=metadata,
                audio_path=audio_path,
                audio_url=audio_url,
                script=script
            )
            
            # 5. Régénération du RSS
            rss_url = await self._regenerate_rss(user_id)
            
            logger.info(f"Podcast briefing généré avec succès: {episode['id']}")
            
            return {
                "status": "success",
                "episode_id": episode["id"],
                "rss_url": rss_url,
                "audio_url": audio_url,
                "message": metadata.get("messages", {}).get("success", {}).get(lang, "Podcast briefing généré avec succès")
            }
            
        except Exception as e:
            logger.error(f"Erreur génération podcast briefing: {e}")
            return {
                "status": "error",
                "message": metadata.get("messages", {}).get("error", {}).get(lang, "Erreur lors de la génération du podcast briefing")
            }
