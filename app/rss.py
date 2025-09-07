"""Génération de flux RSS pour l'application Nestr."""
import logging
from typing import Dict, List, Optional

from .utils import now_utc_rfc822
from .config import settings

logger = logging.getLogger(__name__)


class RSSGenerator:
    """Générateur de flux RSS pour les podcasts Nestr."""
    
    @staticmethod
    def build_rss_xml(
        user_id: str, 
        lang: str, 
        episodes: List[Dict], 
        feed_meta: Optional[Dict] = None
    ) -> bytes:
        """Génère le contenu XML du flux RSS."""
        try:
            logger.info(f"🔧 Génération RSS pour {user_id}: {len(episodes)} épisodes")
            
            # Log des épisodes pour debug
            for i, episode in enumerate(episodes):
                logger.debug(f"  Épisode {i+1}: {episode.get('title', 'Sans titre')} - {episode.get('audio_url', 'Pas d\'URL')}")
            
            # Métadonnées par défaut si non fournies
            if not feed_meta:
                feed_meta = {
                    "feed_title": settings.rss_feed_title.format(user_id=user_id),
                    "feed_description": settings.rss_feed_description.format(user_id=user_id),
                    "feed_author": settings.rss_author,
                    "language": settings.rss_language or lang,
                    "category": settings.rss_category,
                    "cover_url": settings.rss_cover_url,
                    "site_url": settings.rss_site_url,
                    "ttl": settings.rss_ttl_minutes,
                }
            
            # Construire le XML RSS
            xml_content = RSSGenerator._build_rss_header(feed_meta, lang)
            
            # Ajouter les épisodes
            for episode in episodes:
                xml_content += RSSGenerator._build_episode_item(episode, lang)
            
            # Fermer le XML
            xml_content += RSSGenerator._build_rss_footer()
            
            # Encoder en UTF-8
            xml_bytes = xml_content.encode('utf-8')
            
            logger.info(f"RSS XML généré pour {user_id}: {len(episodes)} épisodes, {len(xml_bytes)} bytes")
            return xml_bytes
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du RSS: {e}")
            raise
    
    @staticmethod
    def _build_rss_header(feed_meta: Dict, lang: str) -> str:
        """Construit l'en-tête du flux RSS."""
        title = feed_meta.get("feed_title", "Nestr Podcasts")
        description = feed_meta.get("feed_description", "Podcasts personnalisés Nestr")
        author = feed_meta.get("feed_author", "Nestr")
        category = feed_meta.get("category", "Education")
        cover_url = feed_meta.get("cover_url", "")
        site_url = feed_meta.get("site_url", "")
        ttl_minutes = feed_meta.get("ttl", 60)
        
        # Langue pour le namespace iTunes
        itunes_lang = "fr-fr" if lang == "fr" else "en-us"
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title>{RSSGenerator._escape_xml(title)}</title>
    <description>{RSSGenerator._escape_xml(description)}</description>
    <language>{lang}</language>
    <itunes:language>{itunes_lang}</itunes:language>
    <itunes:author>{RSSGenerator._escape_xml(author)}</itunes:author>
    <itunes:summary>{RSSGenerator._escape_xml(description)}</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:category text="{RSSGenerator._escape_xml(category)}"/>
    {f"<itunes:image href=\"{RSSGenerator._escape_xml(cover_url)}\" />" if cover_url else ""}
    {f"<link>{RSSGenerator._escape_xml(site_url)}</link>" if site_url else ""}
    <lastBuildDate>{now_utc_rfc822()}</lastBuildDate>
    <pubDate>{now_utc_rfc822()}</pubDate>
    <ttl>{ttl_minutes}</ttl>
    <generator>Nestr Noesis API</generator>
"""
    
    @staticmethod
    def _build_episode_item(episode: Dict, lang: str) -> str:
        """Construit un élément d'épisode RSS."""
        title = episode.get("title", "Sans titre")
        summary = episode.get("summary", "")
        audio_url = episode.get("audio_url", "")
        duration_sec = episode.get("duration_sec", 0)
        audio_size_bytes = episode.get("audio_size_bytes", 0)
        published_at = episode.get("published_at")
        episode_id = episode.get("id", "")
        
        # Formater la date de publication
        if published_at:
            try:
                if isinstance(published_at, str):
                    from dateutil import parser
                    published_at = parser.parse(published_at)
                pub_date = published_at.strftime("%a, %d %b %Y %H:%M:%S %z")
            except:
                pub_date = now_utc_rfc822()
        else:
            pub_date = now_utc_rfc822()
        
        # Formater la durée pour iTunes
        duration_formatted = RSSGenerator._format_duration_for_itunes(duration_sec)
        
        # Construire l'élément
        item = f"""    <item>
        <title>{RSSGenerator._escape_xml(title)}</title>
        <description><![CDATA[{summary}]]></description>
        <pubDate>{pub_date}</pubDate>
        <guid isPermaLink="false">{episode_id}</guid>
        <enclosure url="{audio_url}" type="audio/mpeg" length="{audio_size_bytes}"/>
        <itunes:title>{RSSGenerator._escape_xml(title)}</itunes:title>
        <itunes:summary>{RSSGenerator._escape_xml(summary)}</itunes:summary>
        <itunes:duration>{duration_formatted}</itunes:duration>
        <itunes:explicit>false</itunes:explicit>
        <itunes:episodeType>full</itunes:episodeType>
    </item>
"""
        return item
    
    @staticmethod
    def _build_rss_footer() -> str:
        """Construit la fin du flux RSS."""
        return """</channel>
</rss>"""
    
    @staticmethod
    def _escape_xml(text: str) -> str:
        """Échappe les caractères spéciaux XML."""
        if not text:
            return ""
        
        # Remplacements de base pour XML
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&apos;"
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return text
    
    @staticmethod
    def _format_duration_for_itunes(seconds: int) -> str:
        """Formate la durée pour iTunes (HH:MM:SS ou MM:SS)."""
        if seconds < 3600:
            # Format MM:SS
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes:02d}:{remaining_seconds:02d}"
        else:
            # Format HH:MM:SS
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            remaining_seconds = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    
    @staticmethod
    def validate_rss_content(xml_content: bytes) -> bool:
        """Valide basiquement le contenu RSS généré."""
        try:
            content_str = xml_content.decode('utf-8')
            
            # Vérifications basiques
            if not content_str.startswith('<?xml'):
                return False
            
            if '<rss' not in content_str:
                return False
            
            if '<channel>' not in content_str:
                return False
            
            if '</rss>' not in content_str:
                return False
            
            return True
            
        except Exception:
            return False


# Instance globale
rss_generator = RSSGenerator()
