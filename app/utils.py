"""Utility functions for Nestr application."""
from typing import Dict, Any
from datetime import datetime


def default_metadata_for_generation(message: str) -> Dict[str, Any]:
    """Generate default metadata for podcast generation."""
    return {
        "message": message,
        "generated_at": datetime.utcnow().isoformat(),
        "source": "api",
        "version": "1.0.0"
    }


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    import re
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length
    if len(filename) > 100:
        filename = filename[:100]
    return filename


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def generate_episode_id(user_id: str, timestamp: str) -> str:
    """Generate unique episode ID."""
    import hashlib
    content = f"{user_id}-{timestamp}"
    return hashlib.md5(content.encode()).hexdigest()[:12]
