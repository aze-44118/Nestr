"""Dependency injection for Nestr application."""
from typing import Optional
from .config import settings


class OpenAIManager:
    """OpenAI API manager."""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.voice = settings.openai_voice
        self.test_mode = not bool(self.api_key)
    
    def is_available(self) -> bool:
        """Check if OpenAI is available."""
        return not self.test_mode


class SupabaseManager:
    """Supabase database manager."""
    
    def __init__(self):
        self.url = settings.supabase_url
        self.key = settings.supabase_key
        self.test_mode = not bool(self.url and self.key)
        self.client = None
        
        if not self.test_mode:
            try:
                from supabase import create_client, Client
                self.client: Client = create_client(self.url, self.key)
            except ImportError:
                self.test_mode = True
    
    def is_available(self) -> bool:
        """Check if Supabase is available."""
        return not self.test_mode
    
    def resolve_user(self, user_id: str, email: Optional[str] = None, name: Optional[str] = None) -> str:
        """Resolve user ID for database operations."""
        if self.test_mode:
            return f"test-user-{user_id}"
        return str(user_id)


class RSSGenerator:
    """RSS feed generator."""
    
    def __init__(self):
        self.test_mode = True  # Simplified for now
    
    def is_available(self) -> bool:
        """Check if RSS generation is available."""
        return True
    
    def generate_rss_url(self, user_id: str) -> str:
        """Generate RSS URL for user."""
        if self.test_mode:
            return f"https://example.com/rss/{user_id}.xml"
        return f"https://nestr.app/rss/{user_id}.xml"


# Global instances
_openai_manager: Optional[OpenAIManager] = None
_supabase_manager: Optional[SupabaseManager] = None
_rss_generator: Optional[RSSGenerator] = None


def get_openai_manager() -> OpenAIManager:
    """Get OpenAI manager instance."""
    global _openai_manager
    if _openai_manager is None:
        _openai_manager = OpenAIManager()
    return _openai_manager


def get_supabase_manager() -> SupabaseManager:
    """Get Supabase manager instance."""
    global _supabase_manager
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager()
    return _supabase_manager


def get_rss_generator() -> RSSGenerator:
    """Get RSS generator instance."""
    global _rss_generator
    if _rss_generator is None:
        _rss_generator = RSSGenerator()
    return _rss_generator
