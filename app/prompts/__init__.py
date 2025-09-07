"""Module pour charger les prompts OpenAI."""
import os
import json
from pathlib import Path

def load_prompt(prompt_name: str) -> str:
    """Charge un prompt depuis un fichier texte."""
    prompts_dir = Path(__file__).parent
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt '{prompt_name}' not found in {prompts_dir}")
    
    return prompt_file.read_text(encoding='utf-8')

def load_tts_prompt(prompt_name: str) -> str:
    """Charge un prompt TTS depuis le fichier JSON."""
    prompts_dir = Path(__file__).parent
    tts_file = prompts_dir / "prompts_tts.json"
    
    if not tts_file.exists():
        raise FileNotFoundError(f"TTS prompts file not found: {tts_file}")
    
    with open(tts_file, 'r', encoding='utf-8') as f:
        tts_prompts = json.load(f)
    
    if prompt_name not in tts_prompts:
        raise KeyError(f"TTS prompt '{prompt_name}' not found in {tts_file}")
    
    return tts_prompts[prompt_name]

# Alias pour compatibilité
get_prompt = load_prompt

# Prompts disponibles
AVAILABLE_PROMPTS = ["intent", "briefing", "wellness", "other"]
AVAILABLE_TTS_PROMPTS = ["wellness_tts"]
