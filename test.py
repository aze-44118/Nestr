#!/usr/bin/env python3
"""
Test simple de l'API Nestr
"""

import httpx
import json
import uuid

API_URL = "http://localhost:8080"

def test_api():
    """Test complet de l'API."""
    print("🧪 Test de l'API Nestr")
    print("=" * 30)
    
    # Test 1: Santé de l'API
    print("\n1️⃣ Test de santé...")
    try:
        with httpx.Client() as client:
            response = client.get(f"{API_URL}/healthz")
            if response.status_code == 200:
                print("✅ API en ligne")
            else:
                print(f"❌ Erreur: {response.status_code}")
                return
    except Exception as e:
        print(f"💥 Erreur de connexion: {e}")
        return
    
    # Test 2: Génération de podcast
    print("\n2️⃣ Test génération podcast...")
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{API_URL}/webhooks/generate",
                json={
                    "user_id": str(uuid.uuid4()),
                    "message": "Méditation pour dormir",
                    "intent": "wellness",
                    "lang": "fr"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ Podcast généré avec succès")
                print(f"📡 RSS: {result.get('rss_url', 'N/A')}")
                print(f"🎵 Audio: {result.get('audio_url', 'N/A')}")
            else:
                print(f"❌ Erreur {response.status_code}: {response.text}")
                
    except Exception as e:
        print(f"💥 Erreur: {e}")

if __name__ == "__main__":
    test_api()
