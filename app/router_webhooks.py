"""Webhook router for Nestr application."""
from fastapi import APIRouter, HTTPException
from .models import PodcastGenerationRequest, PodcastGenerationResponse
from .deps import get_openai_manager, get_supabase_manager, get_rss_generator
from .pipeline_manager import PipelineManager
from .utils import default_metadata_for_generation

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/generate", response_model=PodcastGenerationResponse)
async def generate_podcast(request: PodcastGenerationRequest):
    """Generate a podcast based on the request."""
    try:
        # Get dependencies
        openai_manager = get_openai_manager()
        supabase_manager = get_supabase_manager()
        rss_generator = get_rss_generator()
        
        # Create pipeline manager
        pipeline_manager = PipelineManager(openai_manager, supabase_manager, rss_generator)
        
        # Generate metadata
        metadata = request.metadata or default_metadata_for_generation(request.message)
        
        # Generate podcast
        result = await pipeline_manager.generate_podcast(
            user_id="api-user",  # Default user for API requests
            message=request.message,
            lang=request.lang,
            intent=request.intent,
            metadata=metadata
        )
        
        return PodcastGenerationResponse(
            status=result["status"],
            message=result["message"],
            episode_title=result.get("episode_title"),
            duration_sec=result.get("duration_sec"),
            rss_url=result.get("rss_url"),
            audio_url=result.get("audio_url")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating podcast: {str(e)}"
        )
