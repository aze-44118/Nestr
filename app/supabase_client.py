"""Client Supabase pour l'application Nestr."""
import json
import logging
from typing import Dict, List, Optional
from uuid import UUID

from supabase import Client, create_client

from .config import settings
from .models import EpisodeDTO
from .utils import make_audio_path, make_rss_path

logger = logging.getLogger(__name__)


class SupabaseManager:
    """Gestionnaire Supabase pour la base de données et le storage."""
    
    def __init__(self):
        """Initialise le client Supabase."""
        self.test_mode = False
        self.client = None
        
        try:
            # Vérifier si on est en mode test
            if (settings.supabase_url == "https://test.supabase.co" or 
                settings.supabase_anon_key == "test_anon_key"):
                logger.info("Mode test détecté - Supabase simulé")
                self.test_mode = True
                return
            
            # Utiliser la clé service_role pour bypasser RLS
            self.client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key  # Utiliser service_role au lieu d'anon
            )
            
            # Vérifier que le bucket existe
            self._ensure_bucket_exists()
            
        except Exception as e:
            logger.error(f"Erreur initialisation Supabase: {e}")
            logger.info("Passage en mode test")
            self.test_mode = True
            self.client = None
    
    def _ensure_bucket_exists(self):
        """Vérifie que le bucket de podcasts existe (sans le créer)."""
        if self.test_mode:
            logger.info("Mode test - Bucket simulé")
            return
            
        try:
            # Vérifier si le bucket existe en essayant de lister ses fichiers
            # Cette méthode évite les problèmes RLS car elle ne fait que lire
            logger.info(f"Vérification de l'existence du bucket {settings.supabase_podcast_bucket}")
            
            # Essayer d'accéder au bucket (sans créer)
            self.client.storage.from_(settings.supabase_podcast_bucket).list()
            logger.info(f"✅ Bucket {settings.supabase_podcast_bucket} existe et est accessible")
                
        except Exception as e:
            # Si le bucket n'existe pas ou n'est pas accessible
            logger.error(f"❌ Bucket {settings.supabase_podcast_bucket} n'existe pas ou n'est pas accessible: {e}")
            logger.error("Veuillez créer le bucket manuellement dans Supabase Dashboard")
            # Ne pas faire échouer l'initialisation, mais log l'erreur
            logger.warning("L'API continuera mais les uploads échoueront")
    

    
    def get_profile(self, user_id: UUID) -> Optional[Dict]:
        """Récupère le profil d'un utilisateur."""
        try:
            # Essayer d'abord la table users
            result = self.client.table("users").select("*").eq("id", str(user_id)).execute()
            if result.data:
                return result.data[0]
            
            # Sinon, essayer la table auth.users (via RPC)
            result = self.client.rpc("get_user_by_id", {"user_id": str(user_id)}).execute()
            if result.data:
                return result.data
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du profil {user_id}: {e}")
            return None
    
    def resolve_user(self, user_id: UUID, user_token: Optional[str] = None, telegram_user_id: Optional[int] = None) -> str:
        """Résout et valide un utilisateur à partir de user_id (requis)."""
        if self.test_mode:
            logger.info(f"Mode test - Utilisateur simulé: {user_id}")
            return str(user_id)
        
        try:
            logger.info(f"Vérification de l'utilisateur {user_id}")
            
            # Vérification simple : on accepte l'user_id s'il est un UUID valide
            # Dans un vrai projet, vous pourriez vérifier contre une table users
            if isinstance(user_id, UUID):
                logger.info(f"✅ Utilisateur valide: {user_id}")
                return str(user_id)
            else:
                raise ValueError(f"Format d'user_id invalide: {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Utilisateur invalide: {e}")
            raise ValueError(f"Utilisateur invalide ou non trouvé: {str(e)}")
    
    def insert_episode(self, episode_data: Dict) -> Dict:
        """Insère un nouvel épisode dans la base de données."""
        if self.test_mode:
            # Mode test : simuler l'insertion
            logger.info(f"🧪 Épisode simulé | {episode_data.get('title', 'N/A')}")
            # Retourner un épisode simulé
            return {
                "id": f"test_episode_{episode_data.get('user_id', 'unknown')}",
                "user_id": episode_data.get("user_id"),
                "title": episode_data.get("title", "Podcast généré"),
                "status": "test"
            }
        
        try:
            logger.debug(f"insert_episode input={episode_data}")
            # Pour les utilisateurs Telegram, on utilise un UUID généré à partir de l'ID Telegram
            if episode_data.get("user_id", "").startswith("telegram_"):
                from uuid import uuid5, NAMESPACE_DNS
                telegram_id = episode_data["user_id"].replace("telegram_", "")
                # Générer un UUID déterministe à partir de l'ID Telegram
                episode_data["user_id"] = str(uuid5(NAMESPACE_DNS, f"telegram_{telegram_id}"))
                logger.info(f"Conversion ID Telegram {telegram_id} -> UUID {episode_data['user_id']}")
            
            logger.debug("insert_episode calling supabase")
            result = self.client.table("episodes").insert(episode_data).execute()
            if result.data:
                logger.info(f"Épisode inséré: {result.data[0]['id']}")
                return result.data[0]
            else:
                raise Exception("Aucun épisode inséré")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion de l'épisode: {e}")
            raise
    
    def list_episodes(self, user_id: str) -> List[Dict]:
        """Liste tous les épisodes d'un utilisateur, triés par date de publication."""
        # SUPPRIMER le mode test pour les épisodes - toujours récupérer les vrais épisodes
        # if self.test_mode:
        #     logger.info(f"🧪 Épisodes simulés | {user_id}")
        #     return []
        
        try:
            # Pour les utilisateurs Telegram, convertir en UUID
            if user_id.startswith("telegram_"):
                from uuid import uuid5, NAMESPACE_DNS
                telegram_id = user_id.replace("telegram_", "")
                user_id = str(uuid5(NAMESPACE_DNS, f"telegram_{telegram_id}"))
                logger.info(f"Conversion ID Telegram {telegram_id} -> UUID {user_id} pour list_episodes")
            
            result = (
                self.client.table("episodes")
                .select("*")
                .eq("user_id", user_id)
                .order("published_at", desc=True)
                .execute()
            )
            episodes = result.data or []
            logger.info(f"📡 Récupéré {len(episodes)} épisodes pour {user_id}")
            return episodes
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des épisodes: {e}")
            # Retourner une liste vide plutôt que de planter
            return []
    
    def upload_public(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload un fichier dans le bucket public."""
        if self.test_mode:
            logger.info(f"Mode test - Upload simulé: {path}")
            return f"https://test.supabase.co/storage/v1/object/public/{settings.supabase_podcast_bucket}/{path}"
        
        try:
            logger.info(f"Upload vers {settings.supabase_podcast_bucket}/{path}")
            
            # Créer un fichier temporaire pour l'upload
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
                temp_file.write(data)
                temp_file.flush()
                
                # Upload le fichier temporaire avec overwrite (upsert) et bon content-type
                with open(temp_file.name, 'rb') as f:
                    result = self.client.storage.from_(settings.supabase_podcast_bucket).upload(
                        path=path,
                        file=f,
                        file_options={
                            "contentType": content_type,
                            "upsert": True
                        }
                    )
                
                # Nettoyer le fichier temporaire
                os.unlink(temp_file.name)
            
            # Vérifier s'il y a une erreur dans la réponse
            if hasattr(result, 'error') and result.error:
                raise Exception(f"Erreur Supabase: {result.error}")
            
            # Construire l'URL publique
            public_url = f"{settings.supabase_url}/storage/v1/object/public/{settings.supabase_podcast_bucket}/{path}"
            logger.info(f"✅ Upload réussi: {public_url}")
            return public_url
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload de {path}: {e}")
            raise
    
    def upload_rss(self, user_id: str, rss_content: bytes) -> str:
        """Upload le fichier RSS d'un utilisateur."""
        rss_path = make_rss_path(user_id)
        
        # TOUJOURS uploader le RSS, même en mode test
        try:
            return self.upload_public(
                rss_path,
                rss_content,
                "application/rss+xml"
            )
        except Exception as e:
            logger.error(f"Erreur upload RSS: {e}")
            # En cas d'erreur, retourner une URL simulée mais log l'erreur
            logger.warning("RSS non uploadé mais génération continuée")
            return f"https://{settings.supabase_url.replace('https://', '')}/storage/v1/object/public/{settings.supabase_podcast_bucket}/{rss_path}"
    
    def get_episode_count(self, user_id: str) -> int:
        """Retourne le nombre d'épisodes d'un utilisateur."""
        try:
            result = (
                self.client.table("episodes")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            return result.count or 0
            
        except Exception as e:
            logger.error(f"Erreur lors du comptage des épisodes: {e}")
            return 0


# Instance globale
supabase_manager = SupabaseManager()
