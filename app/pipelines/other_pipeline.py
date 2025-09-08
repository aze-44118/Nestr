"""Pipeline de génération de podcasts de type other/créatif."""

import logging
from typing import Dict, Any, List

from .base_pipeline import BasePipeline
from app.prompts import load_prompt, load_tts_prompt
from app.config import settings as app_settings
import json

logger = logging.getLogger(__name__)


class OtherPipeline(BasePipeline):
    """Pipeline spécialisé pour les podcasts de type other/créatif."""
    
    async def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère un podcast de type other/créatif.
        
        Caractéristiques :
        - Ton créatif et engageant
        - Contenu adaptatif selon le sujet
        - Focus sur la créativité et l'originalité
        """
        try:
            logger.info(f"Génération podcast other pour user {user_id}")

            # 1) Prompt métier (format JSON dialogué)
            other_system_prompt = load_prompt("other")

            # 2) Génération du script JSON dialogué
            try:
                script_json = await self._generate_other_script(
                    system_prompt=other_system_prompt,
                    message=message,
                    lang=lang or app_settings.gen_default_lang,
                    estimated_duration=metadata.get("estimated_duration_sec", 240),
                )
                # Logs de conformité du script
                try:
                    slug_list_dbg = script_json.get("slug_theme", []) if isinstance(script_json, dict) else []
                    logger.info(
                        f"🧩 Script other JSON reçu | metadata={ 'metadata' in script_json } | segments={ len(slug_list_dbg) if isinstance(slug_list_dbg, list) else 'N/A' }"
                    )
                    if isinstance(slug_list_dbg, list):
                        # Aperçu des 2 premiers segments
                        for i, seg in enumerate(slug_list_dbg[:2]):
                            logger.debug(
                                f"   seg[{i}] speaker={seg.get('speaker')} len={len(seg.get('text',''))} preview={seg.get('text','')[:80].replace('\n',' ')}"
                            )
                except Exception as _:
                    logger.debug("(debug) Impossible de logger les détails du script JSON")
            except Exception:
                # Fallback: script minimal si le LLM ne renvoie pas un JSON valide
                script_json = {"metadata": {"title": metadata.get("episode_title", "Podcast"), "description": metadata.get("episode_summary", "")}, "slug_theme": [
                    {"speaker": "speaker_1", "text": f"Bienvenue sur Nestr. Aujourd'hui, nous parlons de: {message}.", "pause_after_sec": 1},
                    {"speaker": "speaker_2", "text": "Explorons ensemble ce sujet avec clarté et nuance.", "pause_after_sec": 1}
                ]}

            # 3) Prompts TTS par speaker
            prompt_s1 = load_tts_prompt(app_settings.tts_prompt_other_speaker_1)
            prompt_s2 = load_tts_prompt(app_settings.tts_prompt_other_speaker_2)

            # 4) Générer audio segments (sans bruit de fond)
            segments: List[Dict] = []
            slug_list = script_json.get("slug_theme", []) if isinstance(script_json, dict) else []
            if not isinstance(slug_list, list) or len(slug_list) == 0:
                # Fallback: un court dialogue par défaut
                slug_list = [
                    {"speaker": "speaker_1", "text": f"Bienvenue sur Nestr. Sujet: {message}.", "pause_after_sec": 1},
                    {"speaker": "speaker_2", "text": "Commençons par définir les notions clés.", "pause_after_sec": 1}
                ]
            logger.info(f"🎬 Préparation segments TTS | total={len(slug_list)}")
            for idx, seg in enumerate(slug_list):
                speaker = seg.get("speaker", "speaker_1")
                text = seg.get("text", "")
                pause = int(seg.get("pause_after_sec", 0))

                if not text:
                    continue

                # Inverser les voix: speaker_1 -> voix speaker_2, speaker_2 -> voix speaker_1
                if speaker == "speaker_1":
                    voice = app_settings.tts_voice_other_speaker_2
                    tts_prompt = prompt_s1
                else:
                    voice = app_settings.tts_voice_other_speaker_1
                    tts_prompt = prompt_s2

                # Log avant TTS
                logger.info(
                    f"🎙️ TTS input | seg={idx} speaker={speaker} voice={voice} text_len={len(text)} preview={text[:100].replace('\n',' ')}"
                )
                logger.debug(f"🎙️ TTS prompt present={bool(tts_prompt)}")

                # Fallback robuste si la voix spécifiée n'est pas supportée
                try:
                    audio_bytes = self.openai.tts_to_bytes(
                        text=text,
                        model=app_settings.tts_model_other,
                        voice=voice,
                        tts_prompt=tts_prompt,
                    )
                except Exception:
                    # Réessayer avec la voix par défaut
                    audio_bytes = self.openai.tts_to_bytes(
                        text=text,
                        model=app_settings.tts_model_other,
                        voice=app_settings.default_tts_voice,
                        tts_prompt=tts_prompt,
                    )
                segments.append({"type": "speech", "audio": audio_bytes, "pause_after_sec": pause})

            # 5) Assemblage avec mastering audio complet
            final_audio = await self._assemble_dialog_audio(segments)
            logger.info(f"🎧 Audio final assemblé | bytes={len(final_audio)} | segments={len(segments)}")

            # 6) Upload, DB, RSS (communs)
            audio_path, audio_url = await self._upload_audio(user_id, final_audio)
            script_str = json.dumps(script_json, ensure_ascii=False, indent=2)
            episode = await self._save_episode(
                user_id=user_id,
                intent="other",
                lang=lang,
                metadata=metadata,
                audio_path=audio_path,
                audio_url=audio_url,
                script=script_str,
                audio_bytes=final_audio,
            )
            rss_url = await self._regenerate_rss(user_id)
            
            logger.info(f"Podcast other généré avec succès: {episode['id']}")
            
            return {
                "status": "success",
                "episode_id": episode["id"],
                "rss_url": rss_url,
                "audio_url": audio_url,
                "message": metadata.get("messages", {}).get("success", {}).get(lang, "Podcast créatif généré avec succès")
            }
            
        except Exception as e:
            logger.error(f"Erreur génération podcast other: {e}")
            base_msg = metadata.get("messages", {}).get("error", {}).get(lang, "Erreur lors de la génération du podcast créatif")
            return {
                "status": "error",
                "message": f"{base_msg} | {str(e)}" if getattr(app_settings, "debug", False) else base_msg
            }

    async def _generate_other_script(self, system_prompt: str, message: str, lang: str, estimated_duration: int) -> Dict[str, Any]:
        """Génère le JSON dialogué pour 'other' via LLM."""
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"\nMessage utilisateur: {message}\n\nDurée cible: {estimated_duration} secondes\nLangue: {lang}"},
            ],
            "model": app_settings.gen_default_model,
            "max_tokens": 2000,
            "temperature": 0.7,
        }
        resp = await self.openai.chat_json(payload)
        return resp

    async def _assemble_dialog_audio(self, segments: List[Dict[str, Any]]) -> bytes:
        """Assemblage avec mastering audio complet."""
        try:
            from .audio_mastering import AudioMastering
            mastering = AudioMastering()
            return mastering.master_audio(segments)
        except Exception as e:
            logger.warning(f"Mastering échoué, fallback simple: {e}")
            # Fallback simple
            valid_segments = [seg.get("audio") for seg in segments if seg.get("audio")]
            if not valid_segments:
                raise ValueError("Aucun segment audio généré")
            
            combined = bytearray()
            for audio in valid_segments:
                combined.extend(audio)
            return bytes(combined)

    def _export_optimized_mp3(self, audio_data: bytes) -> bytes:
        """Export déjà fait dans le mastering."""
        return audio_data