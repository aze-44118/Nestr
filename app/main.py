"""Main FastAPI application for Nestr - AI-powered podcast generation platform."""
import json
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

from .config import settings
from .models import HealthResponse, TelegramWebhookRequest
from .router_webhooks import router as webhooks_router
from .deps import get_openai_manager, get_supabase_manager, get_rss_generator
from .pipeline_manager import PipelineManager
from .utils import default_metadata_for_generation


# Logging configuration with colors and formats
class ColoredFormatter(logging.Formatter):
    """Colored log formatter for terminal output."""
    
    def __init__(self, use_colors=True, format=None, datefmt=None):
        super().__init__(format, datefmt)
        self.use_colors = use_colors
    
    def format(self, record):
        from .config import LOG_COLORS
        
        # Color based on log level
        if self.use_colors and record.levelname in LOG_COLORS:
            color = LOG_COLORS[record.levelname]
            reset = LOG_COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"
        
        # Format based on log type
        if hasattr(record, 'log_type'):
            if record.log_type == "request":
                return self._format_request(record)
            elif record.log_type == "pipeline":
                return self._format_pipeline(record)
            elif record.log_type == "podcast":
                return self._format_podcast(record)
        
        # Default format
        return super().format(record)
    
    def _format_request(self, record):
        """Special format for HTTP requests."""
        return f"[{record.asctime}] {record.levelname} | HTTP {record.method} {record.url} | {record.status_code} | {record.duration_ms}ms"
    
    def _format_pipeline(self, record):
        """Special format for pipeline logs."""
        return f"[{record.asctime}] {record.levelname} | PIPELINE {record.intent} | {record.message} | {record.duration_ms}ms"
    
    def _format_podcast(self, record):
        """Special format for podcast generation logs."""
        return f"[{record.asctime}] {record.levelname} | PODCAST {record.intent} | User: {record.user_id} | {record.message} | {record.duration_ms}ms"


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production."""
    
    def format(self, record):
        log_entry = {
            "timestamp": record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if they exist
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
        
        # Add exception if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)


def setup_logging():
    """Configure the logging system in a simple way."""
    # Basic logging configuration
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Simple and clear configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
        force=True  # Force reconfiguration
    )
    
    # Main logger
    logger = logging.getLogger("nester")
    
    if settings.debug:
        logger.info("🐛 DEBUG mode enabled")
    else:
        logger.info("🚀 PRODUCTION mode")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    setup_logging()
    logging.info("Nestr application started")
    
    yield
    
    # Shutdown
    logging.info("Nestr application stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Nestr API for AI-powered podcast generation with OpenAI and Supabase",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP: allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all HTTP requests."""
    import time
    start_time = time.time()
    
    # Main logger
    logger = logging.getLogger("nester")
    
    # Log incoming request (simplified)
    if request.url.path != "/healthz":
        logger.info(f"🌐 {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    duration_ms = round(process_time * 1000, 2)
    
    # Log response (only if not health check)
    if request.url.path != "/healthz":
        status_emoji = "✅" if response.status_code < 400 else "❌"
        logger.info(f"{status_emoji} {request.method} {request.url.path} | {response.status_code} | {duration_ms}ms")
    
    return response


# Health check endpoint
@app.get("/healthz", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Application health check endpoint."""
    return HealthResponse(ok=True)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
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


# Telegram webhook endpoint (active only if variables are present)
@app.post("/telegram/webhook", tags=["telegram"]) 
async def telegram_webhook(update: TelegramWebhookRequest):
    """Webhook endpoint for receiving Telegram messages."""
    logger = logging.getLogger("nester")
    
    try:
        # Check Telegram configuration
        if not settings.telegram_token or not settings.telegram_service_id:
            logger.warning("Telegram webhook called but configuration missing. Ignored.")
            return {"ok": True}
        
        # Check if it's a valid message
        if not update.message:
            logger.warning("Invalid Telegram message: no message")
            return {"ok": True}
        
        # Handle non-text messages (stickers, photos, etc.)
        if not update.message.text:
            logger.info(f"Non-text message received from {update.message.from_user.id}, ignored")
            return {"ok": True}
        
        # Get Telegram user ID
        user_id = str(update.message.from_user.id)
        message_text = update.message.text.strip()
        chat_id = update.message.chat.get("id")
        
        logger.info(f"📱 Telegram message received from {user_id} (chat: {chat_id}): {message_text}")
        logger.info(f"🔧 Configuration: token={'***' if settings.telegram_token else 'MISSING'}, service_id={settings.telegram_service_id}")
        
        # Check authentication
        if user_id != settings.telegram_service_id:
            logger.warning(f"🚫 Unauthorized user {user_id}, starting onboarding")
            await handle_unauthorized_user(chat_id, user_id, message_text)
            return {"ok": True}
        
        # User is authorized, process commands
        logger.info(f"✅ Authorized user {user_id}, processing command")
        
        # Parse commands
        if message_text.startswith('/'):
            logger.info(f"🔍 Command detected: {message_text}")
            await handle_telegram_command(chat_id, message_text, user_id)
        else:
            # Non-command message, ignore silently
            logger.info(f"📝 Non-command message ignored: {message_text}")
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"❌ Error in Telegram webhook: {str(e)}")
        return {"ok": False, "error": str(e)}


async def handle_unauthorized_user(chat_id: int, user_id: str, message_text: str):
    """Handle onboarding for unauthorized users."""
    logger = logging.getLogger("nester")
    
    try:
        # Check if it's an onboarding code
        if message_text.isdigit():
            # It's a numeric code, check if it exists in the users table
            if await validate_onboarding_code(message_text):
                # Valid code, send onboarding message
                await send_onboarding_message(chat_id)
                logger.info(f"✅ Valid onboarding code for {user_id}: {message_text}")
            else:
                # Invalid code
                await send_telegram_message(chat_id, "❌ Invalid code. Please enter a valid code or contact the administrator.")
                logger.warning(f"❌ Invalid onboarding code from {user_id}: {message_text}")
        else:
            # First message, ask for code
            await send_telegram_message(chat_id, 
                "🔐 <b>Welcome to Nestr!</b>\n\n"
                "To access the bot, please enter your access code.\n\n"
                "This code corresponds to your ID in our system.\n\n"
                "💡 <i>Simply enter your numeric code</i>"
            )
            logger.info(f"📝 Onboarding code request for {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Error during onboarding for {user_id}: {str(e)}")
        await send_telegram_message(chat_id, "❌ An error occurred. Please try again.")


async def validate_onboarding_code(code: str) -> bool:
    """Validate an onboarding code against the Supabase users table."""
    logger = logging.getLogger("nester")
    
    try:
        # Get Supabase manager
        supabase_manager = get_supabase_manager()
        
        if supabase_manager.test_mode:
            # In test mode, accept any numeric code
            logger.info(f"Test mode - Code accepted: {code}")
            return True
        
        # Check if the code exists in the users table
        result = supabase_manager.client.table("users").select("id").eq("id", code).execute()
        
        if result.data and len(result.data) > 0:
            logger.info(f"✅ Valid onboarding code found: {code}")
            return True
        else:
            logger.warning(f"❌ Onboarding code not found: {code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error validating code {code}: {str(e)}")
        return False


async def send_onboarding_message(chat_id: int):
    """Send the onboarding message with available commands."""
    onboarding_text = """🎉 <b>Welcome to Nestr!</b>

<b>What is Nestr?</b>
Nestr is your personal assistant for creating custom podcasts. I can generate audio episodes on any topic you want.

<b>Available commands:</b>
• <code>/wellness [topic]</code> - Wellness and health podcast
• <code>/briefing [topic]</code> - News and information podcast  
• <code>/other [topic]</code> - Dialogue and discussion podcast
• <code>/help</code> - Show this help

<b>Usage examples:</b>
• <code>/wellness Create a podcast about morning meditation</code>
• <code>/briefing Summarize this week's tech news</code>
• <code>/other Discuss AI trends in 2024</code>

<b>How it works:</b>
1. Choose a podcast type
2. Describe your topic
3. I generate a personalized audio episode
4. The episode is added to your personal RSS feed

🚀 <i>Ready to create your first podcast?</i>"""

    await send_telegram_message(chat_id, onboarding_text)


async def send_telegram_message(chat_id: int, text: str):
    """Send a message via Telegram API."""
    try:
        # If no Telegram config, do nothing
        if not settings.telegram_token:
            logging.getLogger("nester").warning("send_telegram_message called without TELEGRAM_TOKEN. Ignored.")
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
        logger.info(f"📤 Telegram message sent to {chat_id}")
        
    except Exception as e:
        logger = logging.getLogger("nester")
        logger.error(f"❌ Error sending Telegram message: {str(e)}")
        # Don't crash the webhook, just log the error
        return


async def handle_telegram_command(chat_id: int, command: str, user_id: str):
    """Process Telegram commands and generate podcasts."""
    logger = logging.getLogger("nester")
    
    try:
        # Parse command
        parts = command.split(' ', 1)
        cmd = parts[0].lower()
        message = parts[1] if len(parts) > 1 else ""
        
        logger.info(f"🔧 Processing command: '{cmd}' with message: '{message}'")
        
        # Supported commands
        if cmd in ['/wellness', '/briefing', '/other', '/others']:
            # Handle /others -> /other variant
            if cmd == '/others':
                cmd = '/other'
                intent = 'other'
            else:
                intent = cmd[1:]  # Remove the /
            
            if not message:
                await send_telegram_message(chat_id, f"❌ Please provide a message for the {cmd} command\n\nExample: {cmd} Create a podcast about meditation")
                return
            
            # Send confirmation message
            await send_telegram_message(chat_id, f"🎙️ Generating {intent} podcast...\n\n📝 Topic: {message}")
            
            # Generate podcast
            await generate_telegram_podcast(chat_id, user_id, intent, message)
            
        elif cmd == '/help':
            help_text = """🤖 <b>Nestr Bot Commands</b>

<b>Podcast generation:</b>
• <code>/wellness [message]</code> - Wellness podcast
• <code>/briefing [message]</code> - News briefing podcast
• <code>/other [message]</code> - Dialogue podcast
• <code>/others [message]</code> - Alias for /other

<b>Examples:</b>
• <code>/wellness Create a podcast about morning meditation</code>
• <code>/briefing Summarize this week's tech news</code>
• <code>/other Discuss AI trends in 2024</code>
• <code>/others I want a podcast about Tchaikovsky's Symphony No. 5</code>

<b>Other commands:</b>
• <code>/help</code> - Show this help"""
            
            await send_telegram_message(chat_id, help_text)
            
        else:
            await send_telegram_message(chat_id, f"❌ Unknown command: {cmd}\n\nType /help to see available commands.")
            
    except Exception as e:
        logger.error(f"❌ Error processing Telegram command: {str(e)}")
        await send_telegram_message(chat_id, f"❌ Error processing command: {str(e)}")


async def generate_telegram_podcast(chat_id: int, user_id: str, intent: str, message: str):
    """Generate a podcast via Telegram using existing pipelines."""
    logger = logging.getLogger("nester")
    
    try:
        # Get dependencies
        openai_manager = get_openai_manager()
        supabase_manager = get_supabase_manager()
        rss_generator = get_rss_generator()
        
        # Create pipeline manager
        pipeline_manager = PipelineManager(openai_manager, supabase_manager, rss_generator)
        
        # Create stable UUID from Telegram ID
        from uuid import uuid5, NAMESPACE_DNS
        telegram_uuid = uuid5(NAMESPACE_DNS, f"telegram-{user_id}")
        
        # Resolve user with generated UUID
        resolved_user_id = supabase_manager.resolve_user(telegram_uuid, None, None)
        
        # Default metadata
        metadata = default_metadata_for_generation(message)
        
        # Generate podcast
        logger.info(f"🎙️ Generating {intent} podcast for Telegram user {user_id}")
        result = await pipeline_manager.generate_podcast(
            user_id=resolved_user_id,
            message=message,
            lang="fr",  # Default to French
            intent=intent,
            metadata=metadata
        )
        
        if result["status"] == "success":
            # Success
            success_message = f"""✅ <b>{intent.title()} podcast generated successfully!</b>

🎵 <b>Episode:</b> {result.get('episode_title', 'Untitled')}
📊 <b>Duration:</b> {result.get('duration_sec', 0)} seconds
🔗 <b>RSS:</b> {result.get('rss_url', 'N/A')}

The podcast has been added to your personal RSS feed."""
            
            await send_telegram_message(chat_id, success_message)
            logger.info(f"✅ {intent} podcast generated successfully for Telegram user {user_id}")
            
        else:
            # Error
            error_message = f"❌ <b>Error generating {intent} podcast</b>\n\n{result.get('message', 'Unknown error')}"
            await send_telegram_message(chat_id, error_message)
            logger.error(f"❌ Failed to generate {intent} podcast for Telegram user {user_id}: {result.get('message')}")
            
    except Exception as e:
        logger.error(f"❌ Error generating Telegram podcast: {str(e)}")
        await send_telegram_message(chat_id, f"❌ <b>Technical error</b>\n\nAn unexpected error occurred while generating the podcast.")


# Include routers
app.include_router(webhooks_router)


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler to catch all unhandled exceptions."""
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
            "message": "An internal error occurred",
            "detail": str(exc) if settings.debug else "Internal error"
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
