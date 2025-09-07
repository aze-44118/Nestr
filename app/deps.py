"""Dépendances FastAPI pour l'application Nestr."""
from typing import Generator

from fastapi import Depends

from .config import settings
from .openai_client import openai_manager
from .rss import rss_generator
from .supabase_client import supabase_manager


def get_settings():
    """Retourne les paramètres de configuration."""
    return settings


def get_supabase_manager():
    """Retourne le gestionnaire Supabase."""
    return supabase_manager


def get_openai_manager():
    """Retourne le gestionnaire OpenAI."""
    return openai_manager


def get_rss_generator():
    """Retourne le générateur RSS."""
    return rss_generator


# Dépendances pour injection (créées à la demande)
def get_settings_dep():
    return Depends(get_settings)

def get_supabase_manager_dep():
    return Depends(get_supabase_manager)

def get_openai_manager_dep():
    return Depends(get_openai_manager)

def get_rss_generator_dep():
    return Depends(get_rss_generator)
