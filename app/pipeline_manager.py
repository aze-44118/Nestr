"""Gestionnaire centralisé des pipelines de génération de podcasts."""

import logging
from typing import Dict, Any

from .pipelines import BriefingPipeline, WellnessPipeline, OtherPipeline
from .openai_client import OpenAIManager
from .supabase_client import SupabaseManager
from .rss import RSSGenerator

logger = logging.getLogger(__name__)


class PipelineManager:
    """Gestionnaire centralisé pour tous les pipelines de génération."""
    
    def __init__(self, openai_manager: OpenAIManager, supabase_manager: SupabaseManager, rss_generator: RSSGenerator):
        """Initialise le gestionnaire avec les dépendances."""
        self.openai = openai_manager
        self.supabase = supabase_manager
        self.rss_gen = rss_generator
        
        # Initialiser les pipelines
        self.pipelines = {
            "briefing": BriefingPipeline(self.openai, self.supabase, self.rss_gen),
            "wellness": WellnessPipeline(self.openai, self.supabase, self.rss_gen),
            "other": OtherPipeline(self.openai, self.supabase, self.rss_gen)
        }
    
    async def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str, 
        intent: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère un podcast en utilisant le pipeline approprié.
        
        Args:
            user_id: ID de l'utilisateur
            message: Message original de l'utilisateur
            lang: Langue du podcast ("fr" ou "en")
            intent: Type de pipeline ("briefing", "wellness", "other")
            metadata: Métadonnées du podcast
            
        Returns:
            Résultat de la génération du podcast
        """
        try:
            # Vérifier que le pipeline existe
            if intent not in self.pipelines:
                raise ValueError(f"Pipeline inconnu: {intent}")
            
            logger.info(f"Génération podcast via pipeline '{intent}' pour user {user_id}")
            
            # Utiliser le pipeline approprié
            pipeline = self.pipelines[intent]
            result = await pipeline.generate_podcast(user_id, message, lang, metadata)
            
            logger.info(f"Pipeline '{intent}' terminé avec statut: {result.get('status')}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur dans PipelineManager: {e}")
            return {
                "status": "error",
                "message": f"Erreur lors de la génération du podcast: {str(e)}"
            }
    
    def get_available_pipelines(self) -> list[str]:
        """Retourne la liste des pipelines disponibles."""
        return list(self.pipelines.keys())
    
    def get_pipeline_info(self, intent: str) -> Dict[str, Any]:
        """Retourne les informations sur un pipeline spécifique."""
        if intent not in self.pipelines:
            return {"error": f"Pipeline '{intent}' non trouvé"}
        
        pipeline = self.pipelines[intent]
        return {
            "name": intent,
            "class": pipeline.__class__.__name__,
            "description": pipeline.__class__.__doc__ or f"Pipeline pour {intent}"
        }
