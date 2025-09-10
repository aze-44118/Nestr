"""Application principale FastAPI pour Nestr."""
import json
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import logging

from .config import settings
from .models import HealthResponse, TelegramWebhookRequest
from .router_webhooks import router as webhooks_router
from .deps import get_openai_manager, get_supabase_manager, get_rss_generator
from .pipeline_manager import PipelineManager
from .utils import default_metadata_for_generation


# Configuration du logging avec couleurs et formats
class ColoredFormatter(logging.Formatter):
    """Formateur de logs avec couleurs pour le terminal."""
    
    def __init__(self, use_colors=True, format=None, datefmt=None):
        super().__init__(format, datefmt)
        self.use_colors = use_colors
    
    def format(self, record):
        from .config import LOG_COLORS
        
        # Couleur selon le niveau
        if self.use_colors and record.levelname in LOG_COLORS:
            color = LOG_COLORS[record.levelname]
            reset = LOG_COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"
        
        # Format selon le type
        if hasattr(record, 'log_type'):
            if record.log_type == "request":
                return self._format_request(record)
            elif record.log_type == "pipeline":
                return self._format_pipeline(record)
            elif record.log_type == "podcast":
                return self._format_podcast(record)
        
        # Format par défaut
        return super().format(record)
    
    def _format_request(self, record):
        """Format spécial pour les requêtes HTTP."""
        return f"[{record.asctime}] {record.levelname} | HTTP {record.method} {record.url} | {record.status_code} | {record.duration_ms}ms"
    
    def _format_pipeline(self, record):
        """Format spécial pour les pipelines."""
        return f"[{record.asctime}] {record.levelname} | PIPELINE {record.intent} | {record.message} | {record.duration_ms}ms"
    
    def _format_podcast(self, record):
        """Format spécial pour la génération de podcasts."""
        return f"[{record.asctime}] {record.levelname} | PODCAST {record.intent} | User: {record.user_id} | {record.message} | {record.duration_ms}ms"

class JSONFormatter(logging.Formatter):
    """Formateur de logs au format JSON pour la production."""
    
    def format(self, record):
        log_entry = {
            "timestamp": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Ajouter les champs extra s'ils existent
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "intent"):
            log_entry["intent"] = record.intent
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "url"):
            log_entry["url"] = record.url
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        
        # Ajouter l'exception si présente
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


def setup_logging():
    """Configure le système de logging de manière simple."""
    # Configuration basique du logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Configuration simple et claire
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True  # Force la reconfiguration
    )
    
    # Logger principal
    logger = logging.getLogger("nester")
    
    if settings.debug:
        logger.info("🐛 Mode DEBUG activé")
    else:
        logger.info("🚀 Mode PRODUCTION")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application."""
    # Démarrage
    setup_logging()
    logging.info("Application Nestr Noesis démarrée")
    
    yield
    
    # Arrêt
    logging.info("Application Nestr Noesis arrêtée")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API de génération de podcasts Nestr avec OpenAI et Supabase",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: autoriser toutes les origines
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

    # Middleware de logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware pour logger toutes les requêtes HTTP."""
    import time
    start_time = time.time()
    
    # Logger principal
    logger = logging.getLogger("nester")
    
    # Log de la requête entrante (simplifié)
    if request.url.path != "/healthz":
        logger.info(f"🌐 {request.method} {request.url.path}")
    
    # Traitement de la requête
    response = await call_next(request)
    
    # Calcul du temps de traitement
    process_time = time.time() - start_time
    duration_ms = round(process_time * 1000, 2)
    
    # Log de la réponse (seulement si pas de santé)
    if request.url.path != "/healthz":
        status_emoji = "✅" if response.status_code < 400 else "❌"
        logger.info(f"{status_emoji} {request.method} {request.url.path} | {response.status_code} | {duration_ms}ms")
    
    return response


# Endpoint de santé
@app.get("/healthz", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Endpoint de vérification de santé de l'application."""
    return HealthResponse(ok=True)


# Endpoint racine
@app.get("/", tags=["root"])
async def root():
    """Endpoint racine avec informations sur l'API."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "endpoints": {
            "health": "/healthz",
            "docs": "/docs" if settings.debug else "disabled",
            "webhooks": "/webhooks/generate",
            "telegram": "/telegram/webhook" if settings.telegram_token and settings.telegram_service_id else "disabled"
        }
    }


# Telegram webhook endpoint (actif seulement si les variables sont présentes)
@app.post("/telegram/webhook", tags=["telegram"]) 
async def telegram_webhook(update: TelegramWebhookRequest):
    """Endpoint webhook pour recevoir les messages Telegram."""
    logger = logging.getLogger("nester")
    
    try:
        # Vérifier configuration Telegram
        if not settings.telegram_token or not settings.telegram_service_id:
            logger.warning("Webhook Telegram appelé mais configuration manquante. Ignoré.")
            return {"ok": True}
        # Vérifier si c'est un message valide
        if not update.message or not update.message.text:
            return {"ok": True}
        
        # Récupérer l'ID de l'utilisateur Telegram
        user_id = str(update.message.from_user.id)
        message_text = update.message.text.strip()
        chat_id = update.message.chat.get("id")
        
        logger.info(f"📱 Message Telegram reçu de {user_id}: {message_text}")
        
        # Vérifier l'authentification
        if user_id != settings.telegram_service_id:
            logger.warning(f"🚫 Accès refusé pour l'utilisateur Telegram {user_id}")
            try:
                await send_telegram_message(chat_id, "Désolé, c'est une soirée privée et vous n'êtes pas sur la liste")
            except Exception as e:
                logger.warning(f"Impossible d'envoyer le message de refus: {e}")
            return {"ok": True}
        
        # L'utilisateur est autorisé, traiter les commandes
        logger.info(f"✅ Utilisateur autorisé {user_id}, traitement de la commande")
        
        # Parser les commandes
        if message_text.startswith('/'):
            logger.info(f"🔍 Commande détectée: {message_text}")
            await handle_telegram_command(chat_id, message_text, user_id)
        else:
            # Message non-commande, ignorer silencieusement
            logger.info(f"📝 Message non-commande ignoré: {message_text}")
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"❌ Erreur dans le webhook Telegram: {str(e)}")
        return {"ok": False, "error": str(e)}


async def send_telegram_message(chat_id: int, text: str):
    """Envoie un message via l'API Telegram."""
    try:
        # Si pas de config Telegram, ne rien faire
        if not settings.telegram_token:
            logging.getLogger("nester").warning("send_telegram_message appelé sans TELEGRAM_TOKEN. Ignoré.")
            return
        url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            
        logger = logging.getLogger("nester")
        logger.info(f"📤 Message Telegram envoyé à {chat_id}")
        
    except Exception as e:
        logger = logging.getLogger("nester")
        logger.error(f"❌ Erreur envoi message Telegram: {str(e)}")
        raise


async def handle_telegram_command(chat_id: int, command: str, user_id: str):
    """Traite les commandes Telegram et génère des podcasts."""
    logger = logging.getLogger("nester")
    
    try:
        # Parser la commande
        parts = command.split(' ', 1)
        cmd = parts[0].lower()
        message = parts[1] if len(parts) > 1 else ""
        
        logger.info(f"🔧 Traitement commande: '{cmd}' avec message: '{message}'")
        
        # Commandes supportées
        if cmd in ['/wellness', '/briefing', '/other', '/others']:
            # Gérer la variante /others -> /other
            if cmd == '/others':
                cmd = '/other'
                intent = 'other'
            else:
                intent = cmd[1:]  # Enlever le /
            
            if not message:
                await send_telegram_message(chat_id, f"❌ Veuillez fournir un message pour la commande {cmd}\n\nExemple: {cmd} Créez un podcast sur la méditation")
                return
            
            # Envoyer un message de confirmation
            await send_telegram_message(chat_id, f"🎙️ Génération d'un podcast {intent} en cours...\n\n📝 Sujet: {message}")
            
            # Générer le podcast
            await generate_telegram_podcast(chat_id, user_id, intent, message)
            
        elif cmd == '/help':
            help_text = """🤖 <b>Commandes Nestr Bot</b>

<b>Génération de podcasts:</b>
• <code>/wellness [message]</code> - Podcast bien-être
• <code>/briefing [message]</code> - Podcast briefing
• <code>/other [message]</code> - Podcast dialogue
• <code>/others [message]</code> - Alias pour /other

<b>Exemples:</b>
• <code>/wellness Créez un podcast sur la méditation matinale</code>
• <code>/briefing Résumez les actualités tech de cette semaine</code>
• <code>/other Discutez des tendances IA en 2024</code>
• <code>/others Je veux un podcast sur la symphonie numéro 5 de Tchaikovsky</code>

<b>Autres commandes:</b>
• <code>/help</code> - Affiche cette aide"""
            
            await send_telegram_message(chat_id, help_text)
            
        else:
            await send_telegram_message(chat_id, f"❌ Commande inconnue: {cmd}\n\nTapez /help pour voir les commandes disponibles.")
            
    except Exception as e:
        logger.error(f"❌ Erreur traitement commande Telegram: {str(e)}")
        await send_telegram_message(chat_id, f"❌ Erreur lors du traitement de la commande: {str(e)}")


async def generate_telegram_podcast(chat_id: int, user_id: str, intent: str, message: str):
    """Génère un podcast via Telegram en utilisant les pipelines existants."""
    logger = logging.getLogger("nester")
    
    try:
        # Obtenir les dépendances
        openai_manager = get_openai_manager()
        supabase_manager = get_supabase_manager()
        rss_generator = get_rss_generator()
        
        # Créer le gestionnaire de pipelines
        pipeline_manager = PipelineManager(openai_manager, supabase_manager, rss_generator)
        
        # Créer un UUID stable à partir de l'ID Telegram
        from uuid import uuid5, NAMESPACE_DNS
        telegram_uuid = uuid5(NAMESPACE_DNS, f"telegram-{user_id}")
        
        # Résoudre l'utilisateur avec l'UUID généré
        resolved_user_id = supabase_manager.resolve_user(telegram_uuid, None, None)
        
        # Métadonnées par défaut
        metadata = default_metadata_for_generation(message)
        
        # Générer le podcast
        logger.info(f"🎙️ Génération podcast {intent} pour Telegram user {user_id}")
        result = await pipeline_manager.generate_podcast(
            user_id=resolved_user_id,
            message=message,
            lang="fr",  # Par défaut en français
            intent=intent,
            metadata=metadata
        )
        
        if result["status"] == "success":
            # Succès
            success_message = f"""✅ <b>Podcast {intent} généré avec succès!</b>

🎵 <b>Épisode:</b> {result.get('episode_title', 'Sans titre')}
📊 <b>Durée:</b> {result.get('duration_sec', 0)} secondes
🔗 <b>RSS:</b> {result.get('rss_url', 'N/A')}

Le podcast a été ajouté à votre flux RSS personnel."""
            
            await send_telegram_message(chat_id, success_message)
            logger.info(f"✅ Podcast {intent} généré avec succès pour Telegram user {user_id}")
            
        else:
            # Erreur
            error_message = f"❌ <b>Erreur lors de la génération du podcast {intent}</b>\n\n{result.get('message', 'Erreur inconnue')}"
            await send_telegram_message(chat_id, error_message)
            logger.error(f"❌ Échec génération podcast {intent} pour Telegram user {user_id}: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"❌ Erreur génération podcast Telegram: {str(e)}")
        await send_telegram_message(chat_id, f"❌ <b>Erreur technique</b>\n\nUne erreur inattendue s'est produite lors de la génération du podcast.")


# Inclusion des routeurs
app.include_router(webhooks_router)


# Gestionnaire d'erreurs global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire d'erreurs global pour capturer toutes les exceptions non gérées."""
    logging.error(
        json.dumps({
            "action": "unhandled_exception",
            "method": request.method,
            "url": str(request.url),
            "error": str(exc),
            "error_type": type(exc).__name__
        })
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Une erreur interne s'est produite",
            "detail": str(exc) if settings.debug else "Erreur interne"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug,
        log_level="info"
    )
