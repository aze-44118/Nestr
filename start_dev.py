#!/usr/bin/env python3
"""
Script de démarrage pour le développement.
Utilise uvicorn avec reload automatique.
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

# Forcer l'environnement de développement
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"
os.environ["RELOAD"] = "true"

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
