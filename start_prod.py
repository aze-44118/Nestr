#!/usr/bin/env python3
"""
Script de démarrage pour la production.
Utilise gunicorn avec uvicorn workers.
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

# Configuration pour la production
os.environ["ENVIRONMENT"] = "production"
os.environ["DEBUG"] = "false"
os.environ["RELOAD"] = "false"

if __name__ == "__main__":
    import uvicorn
    
    # Configuration pour Railway/Heroku
    port = int(os.environ.get("PORT", 8080))
    host = os.environ.get("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )
