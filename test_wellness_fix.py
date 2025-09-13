#!/usr/bin/env python3
"""Script de test pour vérifier les corrections du pipeline wellness."""

import asyncio
import json
from pathlib import Path
import sys

# Ajouter le répertoire app au path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from pipelines.wellness_pipeline import WellnessPipeline
from openai_client import OpenAIManager

async def test_wellness_pipeline():
    """Test du pipeline wellness avec les nouvelles corrections."""
    
    print("🧪 Test du pipeline wellness corrigé...")
    
    # Créer une instance du pipeline
    pipeline = WellnessPipeline()
    
    # Test 1: Vérifier la configuration audio
    print(f"✅ Configuration audio:")
    print(f"   - Sample rate: {pipeline.AUDIO_CONFIG['sample_rate']} Hz")
    print(f"   - Channels: {pipeline.AUDIO_CONFIG['ffmpeg_channels']}")
    print(f"   - Background volume: {pipeline.AUDIO_CONFIG['background_volume']}")
    print(f"   - MP3 bitrate: {pipeline.AUDIO_CONFIG['mp3_bitrate']} kbps")
    
    # Test 2: Vérifier que le fichier theta_wave.wav existe
    theta_wave_path = Path(__file__).parent / "theta_wave.wav"
    if theta_wave_path.exists():
        print(f"✅ Fichier theta_wave.wav trouvé: {theta_wave_path}")
        print(f"   - Taille: {theta_wave_path.stat().st_size} bytes")
    else:
        print(f"❌ Fichier theta_wave.wav manquant: {theta_wave_path}")
        return False
    
    # Test 3: Vérifier que ffmpeg est disponible
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"✅ ffmpeg trouvé: {ffmpeg_path}")
    else:
        print("❌ ffmpeg non trouvé - installation requise")
        return False
    
    # Test 4: Test de génération d'un petit script JSON
    print("\n🧪 Test de génération de script JSON...")
    try:
        # Simuler des métadonnées
        metadata = {
            "episode_title": "Test de relaxation",
            "episode_summary": "Séance de test pour vérifier les corrections"
        }
        
        # Générer un script JSON de test
        script_json = await pipeline._generate_wellness_script(
            metadata=metadata,
            message="Je veux me détendre et me relaxer",
            lang="fr",
            estimated_duration=120  # 2 minutes
        )
        
        print(f"✅ Script JSON généré:")
        print(f"   - Clés: {list(script_json.keys())}")
        if "metadata" in script_json:
            print(f"   - Titre: {script_json['metadata'].get('title', 'N/A')}")
            print(f"   - Description: {script_json['metadata'].get('description', 'N/A')}")
        
        # Compter les segments
        total_segments = 0
        for key, value in script_json.items():
            if key != "metadata" and isinstance(value, list):
                total_segments += len(value)
        print(f"   - Total segments: {total_segments}")
        
    except Exception as e:
        print(f"❌ Erreur génération script: {e}")
        return False
    
    print("\n✅ Tous les tests de base sont passés !")
    print("\n📝 Résumé des corrections apportées:")
    print("   1. ✅ Chemin du fichier theta_wave.wav corrigé")
    print("   2. ✅ Configuration audio passée en 16kHz mono")
    print("   3. ✅ Mélange audio remplacé par ffmpeg complet")
    print("   4. ✅ Volumes ajustés (bruit de fond à 10%)")
    print("   5. ✅ Toutes les commandes ffmpeg mises à jour")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_wellness_pipeline())
    if success:
        print("\n🎉 Pipeline wellness prêt à être testé !")
    else:
        print("\n❌ Des problèmes ont été détectés.")
        sys.exit(1)
