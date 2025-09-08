#!/usr/bin/env python3
import os
import sys
import glob
import logging
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("test_upload")


def main() -> int:
    project_root = Path(__file__).parent

    # 1) Charger .env
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(".env chargé")
    else:
        logger.warning(".env introuvable, utilisation des variables d'environnement courantes")

    # 2) Vérifier les clés
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    bucket = os.getenv("SUPABASE_PODCAST_BUCKET", "podcasts")
    user_id = os.getenv("TEST_USER_ID", "0bc3ef56-a182-480e-bdb3-4c2b7bd96960")

    if not supabase_url or not supabase_service_role_key:
        logger.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquants")
        return 1

    # 3) Trouver le fichier 20250906*.mp3 à la racine
    matches = sorted(glob.glob(str(project_root / "20250906*.mp3")))
    if not matches:
        logger.error("Aucun fichier 20250906*.mp3 trouvé à la racine du projet")
        return 1
    local_path = Path(matches[0])
    logger.info(f"Fichier local: {local_path}")

    # 4) Créer client Supabase (service role)
    client = create_client(supabase_url, supabase_service_role_key)

    # 5) Chemin de destination
    dest_path = f"{bucket}/{user_id}/{local_path.name}"
    storage = client.storage.from_(bucket)

    # 6) Upload avec upsert et contentType
    logger.info(f"Upload → {dest_path}")
    with open(local_path, "rb") as f:
        try:
            resp = storage.upload(
                path=f"{user_id}/{local_path.name}",
                file=f,
                file_options={
                    "contentType": "audio/mpeg",
                    "upsert": "true",
                },
            )
        except Exception as e:
            logger.error(f"Erreur upload: {e}")
            return 1

    # 7) Vérifier l'erreur éventuelle
    if hasattr(resp, "error") and resp.error:
        logger.error(f"Erreur Supabase: {resp.error}")
        return 1

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{user_id}/{local_path.name}"
    logger.info(f"✅ Upload OK: {public_url}")
    print(public_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())


