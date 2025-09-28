"""Pipeline manager for podcast generation."""
from typing import Dict, Any, Optional
from .deps import OpenAIManager, SupabaseManager, RSSGenerator


class PipelineManager:
    """Manages podcast generation pipelines."""
    
    def __init__(self, openai_manager: OpenAIManager, supabase_manager: SupabaseManager, rss_generator: RSSGenerator):
        self.openai_manager = openai_manager
        self.supabase_manager = supabase_manager
        self.rss_generator = rss_generator
    
    async def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str = "fr", 
        intent: str = "other", 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate a podcast using the specified pipeline."""
        
        try:
            # For now, return a simple mock response
            # In a real implementation, this would:
            # 1. Generate content using OpenAI
            # 2. Convert text to speech
            # 3. Store in Supabase
            # 4. Update RSS feed
            
            if self.openai_manager.test_mode:
                return {
                    "status": "success",
                    "message": "Podcast generated successfully (test mode)",
                    "episode_title": f"Test {intent.title()} Episode",
                    "duration_sec": 120,
                    "rss_url": self.rss_generator.generate_rss_url(user_id),
                    "audio_url": f"https://example.com/audio/{user_id}/test.mp3"
                }
            else:
                # Real implementation would go here
                return {
                    "status": "error",
                    "message": "OpenAI API not configured. Please set OPENAI_API_KEY environment variable."
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error generating podcast: {str(e)}"
            }
