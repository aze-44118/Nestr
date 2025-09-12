# Makefile pour Nestr Noesis API

.PHONY: help setup dev stop clean test

# Variables
PYTHON = python3
VENV = venv
PIP = $(VENV)/bin/pip
PYTHON_VENV = $(VENV)/bin/python

# Couleurs pour les messages
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m # No Color

help: ## Affiche cette aide
	@echo "$(GREEN)Nestr Noesis API - Commandes disponibles:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(NC) %s\n", $$1, $$2}'

setup: ## Installe les dépendances et configure l'environnement
	@echo "$(GREEN)🔧 Configuration de l'environnement...$(NC)"
	$(PYTHON) -m venv $(VENV) --without-pip
	@echo "$(YELLOW)📦 Installation de pip...$(NC)"
	@if command -v curl >/dev/null 2>&1; then \
		curl -s https://bootstrap.pypa.io/get-pip.py | $(PYTHON_VENV); \
	else \
		echo "$(YELLOW)⚠️  curl non disponible, tentative avec wget...$(NC)"; \
		wget -qO- https://bootstrap.pypa.io/get-pip.py | $(PYTHON_VENV); \
	fi
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Installation terminée$(NC)"
	@echo "$(YELLOW)📝 N'oubliez pas de copier env.example vers .env et de configurer vos clés API$(NC)"

dev: ## Démarre l'API en mode développement
	@echo "$(GREEN)🚀 Démarrage en mode DÉVELOPPEMENT...$(NC)"
	@if [ ! -d "$(VENV)" ]; then echo "$(RED)❌ Environnement virtuel non trouvé. Exécutez 'make setup' d'abord.$(NC)"; exit 1; fi
	@if [ ! -f .env ] && [ -f env.example ]; then cp env.example .env; echo "$(YELLOW)⚠️  .env absent → copie de env.example effectuée$(NC)"; fi
	@echo "$(GREEN)▶️  Lancement Uvicorn (sans reload / sans uvloop)$(NC)"
	UVICORN_NO_UVLOOP=1 $(PYTHON_VENV) -m uvicorn app.main:app \
		--host 127.0.0.1 \
		--port 8080 \
		--loop asyncio \
		--http h11 \
		--no-access-log \
		--log-level info

stop: ## Arrête tous les processus de l'API
	@echo "$(RED)🛑 Arrêt des processus...$(NC)"
	@pkill -f "uvicorn" || true
	@pkill -f "start_dev.py" || true
	@echo "$(GREEN)✅ Processus arrêtés$(NC)"

clean: ## Nettoie les fichiers temporaires et caches
	@echo "$(YELLOW)🧹 Nettoyage...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Nettoyage terminé$(NC)"

test: ## Lance les tests de l'API
	@echo "$(GREEN)🧪 Lancement des tests...$(NC)"
	@if [ ! -d "$(VENV)" ]; then echo "$(RED)❌ Environnement virtuel non trouvé. Exécutez 'make setup' d'abord.$(NC)"; exit 1; fi
	$(PYTHON_VENV) test.py