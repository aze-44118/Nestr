"""Routeur des webhooks pour l'application Nestr."""
import logging
import time
from typing import Dict

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from .deps import get_openai_manager, get_supabase_manager, get_rss_generator
from .models import GenerateRequest, GenerateResponse
from .openai_client import OpenAIManager as OpenAIManagerType
from .supabase_client import SupabaseManager as SupabaseManagerType
from .rss import RSSGenerator as RSSGeneratorType
from .pipeline_manager import PipelineManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_podcast(
    request: GenerateRequest,
    supabase: SupabaseManagerType = Depends(get_supabase_manager),
    openai: OpenAIManagerType = Depends(get_openai_manager),
    rss_gen: RSSGeneratorType = Depends(get_rss_generator),
):
    """Génère un podcast complet via les pipelines centralisés."""
    
    start_time = time.time()
    user_id = None
    
    # Logger principal
    logger = logging.getLogger("nester")
    
    try:
        # 1. Vérification et résolution de l'utilisateur
        logger.info(f"🎙️ Génération podcast | {request.intent} | {request.lang}")
        logger.info(f"📝 Message: {request.message[:50]}{'...' if len(request.message) > 50 else ''}")
        
        try:
            user_id = supabase.resolve_user(request.user_id, request.user_token, None)
            logger.info(f"👤 Utilisateur: {user_id}")
        except Exception as e:
            logger.error(f"❌ Utilisateur invalide: {e}")
            raise HTTPException(status_code=400, detail=f"Utilisateur invalide ou non trouvé: {str(e)}")
        
        # 2. Validation de l'intent
        if request.intent not in ["briefing", "wellness", "other"]:
            logger.error(f"❌ Intent invalide: {request.intent}")
            raise HTTPException(status_code=400, detail="Intent invalide. Valeurs acceptées: briefing, wellness, other")
        
        # 3. Génération via pipeline centralisé
        pipeline_start = time.time()
        try:
            logger.info(f"🔄 Pipeline {request.intent}...")
            
            # Créer le gestionnaire de pipelines
            pipeline_manager = PipelineManager(openai, supabase, rss_gen)
            
            # Générer le podcast via le pipeline approprié
            from .utils import default_metadata_for_generation
            default_metadata = default_metadata_for_generation(request.message)
            
            result = await pipeline_manager.generate_podcast(
                user_id=user_id,
                message=request.message,
                lang=request.lang,
                intent=request.intent,
                metadata=default_metadata
            )
            
            pipeline_ms = int((time.time() - pipeline_start) * 1000)
            
            # Log structuré pour le pipeline
            log_record = logging.LogRecord(
                name="nester",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg=f"✅ Pipeline {request.intent} terminé | {pipeline_ms}ms",
                args=(),
                exc_info=None
            )
            log_record.log_type = "pipeline"
            log_record.intent = request.intent
            log_record.message = f"Pipeline {request.intent} exécuté avec succès"
            log_record.duration_ms = pipeline_ms
            
            logger.handle(log_record)
            
        except Exception as e:
            logger.error(f"❌ Erreur pipeline {request.intent}: {e}")
            raise HTTPException(status_code=500, detail="Erreur lors de la génération du podcast")
        
        # 4. Vérifier le résultat du pipeline
        if result["status"] != "success":
            logger.error(f"❌ Pipeline {request.intent} échoué: {result.get('message', 'Erreur inconnue')}")
            raise HTTPException(status_code=500, detail=result.get("message", "Erreur lors de la génération"))
        
        # 5. Réponse de succès
        total_time = int((time.time() - start_time) * 1000)
        
        # Log de succès avec métriques détaillées
        log_record = logging.LogRecord(
            name="nester",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"🎉 Podcast généré avec succès | User: {user_id} | Intent: {request.intent} | Durée: {total_time}ms",
            args=(),
            exc_info=None
        )
        log_record.log_type = "podcast"
        log_record.user_id = user_id
        log_record.intent = request.intent
        log_record.message = f"Podcast {request.intent} généré avec succès"
        log_record.duration_ms = total_time
        
        logger.handle(log_record)
        
        logger.info(f"📊 Métriques finales:")
        logger.info(f"   • Utilisateur: {user_id}")
        logger.info(f"   • Intent: {request.intent}")
        logger.info(f"   • Langue: {request.lang}")
        logger.info(f"   • Durée totale: {total_time}ms")
        logger.info(f"   • Episode ID: {result.get('episode_id', 'N/A')}")
        logger.info(f"   • RSS URL: {result.get('rss_url', 'N/A')}")
        
        return GenerateResponse(
            status="ok",
            rss_url=result.get("rss_url"),
            message=result.get("message", "Podcast généré avec succès !")
        )
        
    except HTTPException:
        # Ré-élever les HTTPException
        raise
        
    except Exception as e:
        # Gestion des erreurs inattendues
        total_time = int((time.time() - start_time) * 1000)
        
        # Message d'erreur par défaut
        error_message = "Une erreur inattendue s'est produite"
        
        # Log d'erreur détaillé
        logger.error(f"💥 Erreur fatale lors de la génération:")
        logger.error(f"   • User: {user_id}")
        logger.error(f"   • Intent: {request.intent}")
        logger.error(f"   • Durée: {total_time}ms")
        logger.error(f"   • Erreur: {str(e)}")
        
        raise HTTPException(status_code=500, detail=error_message)
