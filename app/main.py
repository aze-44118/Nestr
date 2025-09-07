"""Application principale FastAPI pour Nestr."""
import json
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .models import HealthResponse
from .router_webhooks import router as webhooks_router


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
            "webhooks": "/webhooks/generate"
        }
    }


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
