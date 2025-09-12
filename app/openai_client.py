"""Client OpenAI pour l'application Nestr."""
import json
import logging
import tempfile
from typing import Dict, Optional

import httpx
from openai import OpenAI

from .config import (
    get_prompt,
    settings,
)
from .prompts import load_tts_prompt

logger = logging.getLogger(__name__)


class OpenAIManager:
    """Gestionnaire OpenAI pour l'IA et la synthèse vocale."""
    
    def __init__(self):
        """Initialise le client OpenAI."""
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    def _call_openai(
        self, 
        prompt_type: str, 
        user_content: str,
        **format_kwargs
    ) -> str:
        """
        Méthode centralisée pour tous les appels OpenAI.
        
        Args:
            prompt_type: "intent", "briefing", "wellness", ou "other"
            user_content: Contenu du message utilisateur
            **format_kwargs: Variables pour le formatage du prompt (ex: estimated_duration_sec)
        
        Returns:
            Réponse textuelle d'OpenAI
        """
        try:
            # Récupérer le prompt approprié
            try:
                prompt_template = get_prompt(prompt_type)
            except FileNotFoundError:
                raise ValueError(f"Type de prompt invalide: {prompt_type}")
            
            # Formater le prompt avec les variables
            system_prompt = prompt_template.format(**format_kwargs)
            logger.debug(
                json.dumps({
                    "action": "openai_prompt_prepared",
                    "prompt_type": prompt_type,
                    "format_kwargs": format_kwargs,
                    "system_prompt_len": len(system_prompt)
                })
            )
            
            # Appel OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3 if prompt_type == "intent" else 0.7,
                max_tokens=1000 if prompt_type == "intent" else 2000
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI {prompt_type} call successful, response length: {len(content)}")
            logger.debug(
                json.dumps({
                    "action": "openai_response_received",
                    "prompt_type": prompt_type,
                    "content_preview": content[:200]
                })
            )
            
            return content
            
        except Exception as e:
            logger.error(f"Erreur lors de l'appel OpenAI ({prompt_type}): {e}")
            raise
    
    def detect_intent(self, message: str, lang: str) -> Dict:
        """Détecte l'intention d'un message utilisateur."""
        try:
            content = self._call_openai(
                prompt_type="intent",
                user_content=message
            )
            
            # Valider que c'est du JSON valide
            try:
                result = json.loads(content)
                
                # Validation basique des clés requises
                required_keys = ["intent", "metadata", "messages"]
                if not all(key in result for key in required_keys):
                    raise ValueError("Clés manquantes dans la réponse")
                
                # Validation de l'intent
                if result["intent"] not in ["briefing", "wellness", "other"]:
                    raise ValueError("Intent invalide")
                
                logger.info(f"Intention détectée: {result['intent']}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Réponse OpenAI non-JSON: {content}")
                raise ValueError(f"Réponse non-JSON: {e}")
                
        except Exception as e:
            logger.error(f"Erreur lors de la détection d'intention: {e}")
            raise
    
    def generate_script(
        self, 
        intent: str, 
        metadata: Dict, 
        message: str, 
        lang: str,
        estimated_duration: int
    ) -> str:
        """Génère un script de podcast selon l'intention."""
        try:
            # Préparer le contexte utilisateur
            user_context = f"""
Message utilisateur: {message}

Métadonnées:
- Titre: {metadata.get('episode_title', 'N/A')}
- Résumé: {metadata.get('episode_summary', 'N/A')}
- Durée cible: {estimated_duration} secondes
"""
            
            # Appel centralisé
            logger.debug(json.dumps({
                "action": "generate_script_start",
                "intent": intent,
                "estimated_duration": estimated_duration
            }))
            script = self._call_openai(
                prompt_type=intent,
                user_content=user_context,
                estimated_duration_sec=estimated_duration
            )
            
            logger.info(f"Script généré pour intent '{intent}', longueur: {len(script)} caractères")
            logger.debug(json.dumps({
                "action": "generate_script_done",
                "intent": intent,
                "script_preview": script[:200]
            }))
            return script
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du script: {e}")
            raise
    
    def tts_to_bytes(
        self, 
        text: str, 
        model: Optional[str] = None, 
        voice: Optional[str] = None,
        tts_prompt: Optional[str] = None
    ) -> bytes:
        """Convertit du texte en audio via OpenAI TTS."""
        try:
            model = model or settings.default_tts_model
            voice = voice or settings.default_tts_voice
            
            logger.info(f"🎵 TTS | {model} | {voice}")
            logger.debug(
                json.dumps({
                    "action": "tts_input",
                    "text_len": len(text or ""),
                    "text_preview": (text or "")[:120].replace("\n", " "),
                    "tts_prompt_present": bool(tts_prompt),
                })
            )
            
            # Préparer le texte: ne pas injecter le prompt TTS dans le texte lu
            input_text = text
            if tts_prompt:
                logger.debug(f"TTS prompt fourni (non lu): {tts_prompt[:50]}...")
            
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=input_text
            )
            
            # Sauvegarder temporairement en WAV pour meilleure qualité
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                response.stream_to_file(temp_file.name)
                temp_file.seek(0)
                audio_bytes = temp_file.read()
            
            logger.info(f"✅ Audio généré | {len(audio_bytes)} bytes")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération TTS: {e}")
            raise
    
    async def chat_json(self, payload: Dict) -> Dict:
        """Effectue un appel chat.completions et renvoie un dictionnaire JSON parsé.
        Attendu: le modèle doit répondre par un JSON valide en content.
        """
        try:
            # Forcer le format JSON si non fourni
            payload = dict(payload)
            if "response_format" not in payload:
                payload["response_format"] = {"type": "json_object"}
            # Baisser la température pour plus de conformité JSON si non spécifié
            payload.setdefault("temperature", 0.2)
            response = self.client.chat.completions.create(**payload)
            content = response.choices[0].message.content.strip()
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Réponse non-JSON: {content[:500]}...")
                raise ValueError(f"Réponse non-JSON d'OpenAI: {e}")
            return data
        except Exception as e:
            logger.error(f"Erreur chat_json OpenAI: {e}")
            raise
    
    def _get_wellness_prompt(self) -> str:
        """Récupère le prompt wellness spécialisé."""
        return get_prompt("wellness")
    
    def estimate_duration(self, text: str, lang: str) -> int:
        """Estime la durée d'un texte en secondes (approximation)."""
        # Approximation basée sur la langue et la longueur du texte
        # Français: ~150 mots/minute, Anglais: ~130 mots/minute
        words_per_minute = 150 if lang == "fr" else 130
        
        word_count = len(text.split())
        duration_minutes = word_count / words_per_minute
        
        return max(30, int(duration_minutes * 60))  # Minimum 30 secondes


# Instance globale
openai_manager = OpenAIManager()
