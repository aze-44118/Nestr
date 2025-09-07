"""Pipeline de génération de podcasts de type wellness."""

import logging
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from .base_pipeline import BasePipeline
from app.prompts import load_tts_prompt

logger = logging.getLogger(__name__)


class WellnessPipeline(BasePipeline):
    """Pipeline spécialisé pour les podcasts de type wellness/méditation."""
    
    # Configuration audio optimisée pour réduire la taille des fichiers
    AUDIO_CONFIG = {
        "sample_rate": 22050,     # Réduit de 44.1kHz à 22kHz
        "background_volume": 0.95,
        "tts_volume_boost": 1.2,
        "save_wav": False,        # Désactive WAV (gros gain)
        "save_mp3": True,
        "mp3_bitrate": 64,        # Bitrate réduit pour compression
        # Nouveau: options ffmpeg
        "ffmpeg_enable": True,       # tente ffmpeg d'abord
        "ffmpeg_channels": 1,        # mono recommandé pour voix
        "ffmpeg_vbr_q": 5,           # VBR (2=meilleur, 9=plus petit); 5 ~ 45-56 kbps
        "ffmpeg_cbr_kbps": 48,       # CBR alternatif si vous préférez
        "ffmpeg_use_vbr": True       # True pour VBR, False pour CBR
    }
    
    # Réglage du volume du bruit de fond (0.0 = silence, 1.0 = volume normal)
    BACKGROUND_VOLUME = 0.9  # 30% du volume pour le bruit de fond
    
    async def generate_podcast(
        self, 
        user_id: str, 
        message: str, 
        lang: str, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Génère un podcast de type wellness avec JSON structuré.
        
        Caractéristiques :
        - Traitement JSON avec catégories et pauses
        - Bruit de fond theta_wave.mp3
        - Génération phrase par phrase
        """
        try:
            logger.info(f"🎯 Pipeline wellness | {user_id}")
            
            # 1. Génération du script JSON
            logger.info("📝 Génération script JSON...")
            script_json = await self._generate_wellness_script(
                metadata=metadata,
                message=message,
                lang=lang,
                estimated_duration=metadata.get("estimated_duration_sec", 600)  # 10 min par défaut
            )
            
            # 2. Génération de l'audio avec bruit de fond
            logger.info("🎵 Génération audio avec bruit de fond...")
            raw_audio_bytes = await self._generate_wellness_audio(script_json)
            
            # 2.5. Optimisation MP3 pour réduire la taille
            logger.info("🎵 Optimisation MP3...")
            audio_bytes = self._export_optimized_mp3(raw_audio_bytes)
            
            # 3. Upload de l'audio
            logger.info("☁️ Upload audio...")
            audio_path, audio_url = await self._upload_audio(user_id, audio_bytes)
            
            # 4. Sauvegarde de l'épisode
            logger.info("💾 Sauvegarde épisode...")
            episode = await self._save_episode(
                user_id=user_id,
                intent="wellness",
                lang=lang,
                metadata=metadata,
                audio_path=audio_path,
                audio_url=audio_url,
                script=json.dumps(script_json, ensure_ascii=False, indent=2),
                audio_bytes=audio_bytes
            )
            
            # 5. Régénération du RSS
            logger.info("📡 Génération RSS...")
            rss_url = await self._regenerate_rss(user_id)
            
            logger.info(f"✅ Podcast wellness généré | {episode['id']}")
            
            return {
                "status": "success",
                "episode_id": episode["id"],
                "rss_url": rss_url,
                "audio_url": audio_url,
                "message": metadata.get("messages", {}).get("success", {}).get(lang, "Podcast wellness généré avec succès")
            }
            
        except Exception as e:
            logger.error(f"Erreur génération podcast wellness: {e}")
            return {
                "status": "error",
                "message": metadata.get("messages", {}).get("error", {}).get(lang, "Erreur lors de la génération du podcast wellness")
            }

    async def _generate_wellness_script(self, metadata: Dict, message: str, lang: str, estimated_duration: int) -> Dict:
        """Génère le script JSON pour wellness."""
        try:
            # Préparer le contexte utilisateur pour le prompt wellness
            user_context = f"""
Message utilisateur: {message}

Métadonnées:
- Titre: {metadata.get('episode_title', 'N/A')}
- Résumé: {metadata.get('episode_summary', 'N/A')}
- Durée cible: {estimated_duration} secondes
"""
            
            # Appel OpenAI avec le prompt wellness
            response = self.openai.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.openai._get_wellness_prompt()},
                    {"role": "user", "content": user_context}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"Script JSON wellness généré, longueur: {len(content)} caractères")
            
            # Parser le JSON
            try:
                script_data = json.loads(content)
                logger.info(f"✅ JSON wellness parsé avec succès")
                
                # Extraire les métadonnées générées par le LLM
                if "metadata" in script_data:
                    llm_metadata = script_data["metadata"]
                    logger.info(f"📝 Métadonnées LLM - Titre: {llm_metadata.get('title', 'N/A')}")
                    logger.info(f"📝 Métadonnées LLM - Description: {llm_metadata.get('description', 'N/A')}")
                    
                    # Mettre à jour les métadonnées avec les valeurs du LLM
                    metadata["episode_title"] = llm_metadata.get("title", metadata.get("episode_title", "Podcast généré"))
                    metadata["episode_summary"] = llm_metadata.get("description", metadata.get("episode_summary", ""))
                
                return script_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Erreur parsing JSON wellness: {e}")
                logger.error(f"Contenu reçu: {content[:500]}...")
                raise ValueError(f"JSON invalide reçu du LLM: {e}")
                
        except Exception as e:
            logger.error(f"Erreur génération script wellness: {e}")
            raise

    async def _generate_wellness_audio(self, script_json: Dict) -> bytes:
        """Génère l'audio wellness avec bruit de fond."""
        try:
            # Charger le bruit de fond theta_wave.mp3
            theta_wave_path = Path(__file__).parent.parent.parent / "theta_wave.mp3"
            if not theta_wave_path.exists():
                raise FileNotFoundError(f"Fichier theta_wave.mp3 non trouvé: {theta_wave_path}")
            
            logger.info("🎵 Chargement du bruit de fond theta_wave.mp3...")
            with open(theta_wave_path, 'rb') as f:
                theta_wave_bytes = f.read()
            
            # Traiter chaque thème du JSON
            all_audio_segments = []
            total_duration = 0
            
            for theme_slug, segments in script_json.items():
                if theme_slug == "metadata":
                    continue  # Ignorer les métadonnées
                    
                logger.info(f"🎯 Traitement du thème: {theme_slug}")
                
                for i, segment in enumerate(segments):
                    category = segment.get("category", "unknown")
                    text = segment.get("text", "")
                    pause_after = segment.get("pause_after_sec", 0)
                    
                    logger.info(f"   [{category}] {text[:50]}{'...' if len(text) > 50 else ''}")
                    
                    # Générer l'audio pour le texte (si pas vide)
                    if text.strip():
                        # Charger le prompt TTS wellness
                        tts_prompt = load_tts_prompt("wellness_tts")
                        
                        # Générer l'audio TTS avec le prompt
                        logger.info(f"🎵 TTS | gpt-4o-mini-tts | alloy")
                        audio_bytes = self.openai.tts_to_bytes(text, tts_prompt=tts_prompt)
                        logger.info(f"✅ Audio généré | {len(audio_bytes)} bytes")
                        all_audio_segments.append({
                            "audio": audio_bytes,
                            "duration": len(audio_bytes) / 16000,  # Estimation basique
                            "type": "speech",
                            "category": category
                        })
                        total_duration += len(audio_bytes) / 16000
                    
                    # Ajouter la pause
                    if pause_after > 0:
                        all_audio_segments.append({
                            "audio": None,  # Silence
                            "duration": pause_after,
                            "type": "silence",
                            "category": "pause"
                        })
                        total_duration += pause_after
            
            logger.info(f"🎵 Total segments: {len(all_audio_segments)}, durée estimée: {total_duration:.1f}s")
            
            # Assembler l'audio final avec bruit de fond
            final_audio = await self._assemble_wellness_audio(all_audio_segments, theta_wave_bytes, total_duration)
            
            logger.info(f"✅ Audio wellness assemblé: {len(final_audio)} bytes")
            return final_audio
            
        except Exception as e:
            logger.error(f"Erreur génération audio wellness: {e}")
            raise
    
    def _calculate_audio_duration(self, audio_bytes: bytes) -> int:
        """Calcule la durée réelle d'un fichier audio MP3."""
        try:
            from mutagen.mp3 import MP3
            import io
            
            # Créer un objet MP3 à partir des bytes
            audio_file = io.BytesIO(audio_bytes)
            mp3 = MP3(audio_file)
            
            # Retourner la durée en secondes
            duration_sec = int(mp3.info.length)
            logger.info(f"Durée audio calculée: {duration_sec}s")
            return duration_sec
            
        except Exception as e:
            logger.warning(f"Impossible de calculer la durée audio: {e}")
            # Estimation basique : 1 seconde pour 16KB
            return len(audio_bytes) // 16000

    async def _assemble_wellness_audio(
        self, 
        segments: List[Dict], 
        theta_wave_bytes: bytes, 
        total_duration: float,
        background_volume: float = 0.3  # Nouveau paramètre
    ) -> bytes:
        """Assemble l'audio final avec bruit de fond et pauses respectées."""
        try:
            import io
            import logging
            import struct
            
            logger = logging.getLogger(__name__)
            
            logger.info("🎵 Assemblage audio avec bruit de fond theta et pauses")
            
            # Paramètres audio optimisés pour réduire la taille
            SAMPLE_RATE = self.AUDIO_CONFIG["sample_rate"]  # 22050 Hz au lieu de 48000
            BYTES_PER_SECOND = SAMPLE_RATE * 2  # 16-bit stereo
            
            # Charger le bruit de fond theta
            theta_wave = theta_wave_bytes
            
            # Calculer la durée totale nécessaire
            background_duration = 60 + total_duration + 60  # 60s avant + audio + 60s après
            logger.info(f"🎵 Durée bruit de fond nécessaire: {background_duration}s")
            
            # Étendre le bruit de fond theta si nécessaire
            if len(theta_wave) < background_duration * BYTES_PER_SECOND:
                # Répéter le bruit de fond
                repeats = int(background_duration * BYTES_PER_SECOND / len(theta_wave)) + 1
                theta_wave = theta_wave * repeats
                logger.info(f"🔄 Bruit de fond répété {repeats} fois")
            
            # Couper à la durée exacte
            theta_wave = theta_wave[:int(background_duration * BYTES_PER_SECOND)]
            
            # Créer l'audio de base (bruit de fond)
            final_audio = bytearray(theta_wave)
            
            # Position de départ pour les phrases (60s après le début)
            current_position = 60 * BYTES_PER_SECOND  # 60 secondes en bytes
            
            # Traiter chaque segment
            for segment in segments:
                if segment["type"] == "speech" and segment["audio"]:
                    # Ajouter l'audio TTS à la position actuelle
                    speech_audio = segment["audio"]
                    
                    # Mélanger avec le bruit de fond optimisé
                    background_vol = self.AUDIO_CONFIG["background_volume"]
                    tts_boost = self.AUDIO_CONFIG["tts_volume_boost"]
                    
                    for i, byte in enumerate(speech_audio):
                        if current_position + i < len(final_audio):
                            # Appliquer le volume au bruit de fond
                            background_byte = int(final_audio[current_position + i] * background_vol)
                            
                            # Boost de la voix TTS
                            boosted_tts = min(255, int(byte * tts_boost))
                            
                            # Mélange optimisé : voix boostée + bruit de fond atténué
                            new_byte = min(255, boosted_tts + background_byte)
                            final_audio[current_position + i] = new_byte
                    
                    # Avancer la position
                    current_position += len(speech_audio)
                    logger.debug(f"   Ajouté: {segment['category']} à {current_position/BYTES_PER_SECOND:.1f}s")
                
                elif segment["type"] == "silence":
                    # Avancer la position pour le silence (garder le bruit de fond)
                    silence_duration = segment.get("duration", 0)
                    current_position += int(silence_duration * BYTES_PER_SECOND)
                    logger.debug(f"  ⏸️ Silence: {silence_duration}s à {current_position/BYTES_PER_SECOND:.1f}s")
                
                # Gérer les pauses après chaque segment
                pause_duration = segment.get("pause_after_sec", 0)
                if pause_duration > 0:
                    current_position += int(pause_duration * BYTES_PER_SECOND)
                    logger.debug(f"  ⏸️ Pause: {pause_duration}s à {current_position/BYTES_PER_SECOND:.1f}s")
            
            logger.info(f"✅ Audio final assemblé: {len(final_audio)} bytes")
            return bytes(final_audio)
            
        except Exception as e:
            logger.error(f"Erreur assemblage audio wellness: {e}")
            raise
    
    def _encode_mp3_ffmpeg(self, raw_pcm: bytes, sample_rate: int, channels: int) -> Optional[bytes]:
        import shutil, subprocess

        if not self.AUDIO_CONFIG.get("ffmpeg_enable", True):
            return None

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return None

        # Préparer commande ffmpeg: entrée PCM s16le (little-endian), sortie MP3
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-f", "s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-i", "pipe:0",
            "-vn",
            "-ac", str(self.AUDIO_CONFIG.get("ffmpeg_channels", 1)),
            "-ar", str(sample_rate),
        ]

        if self.AUDIO_CONFIG.get("ffmpeg_use_vbr", True):
            # VBR: qualité perceptuelle meilleure à taille équivalente
            q = int(self.AUDIO_CONFIG.get("ffmpeg_vbr_q", 5))
            cmd += ["-q:a", str(q)]
        else:
            # CBR
            kbps = int(self.AUDIO_CONFIG.get("ffmpeg_cbr_kbps", 48))
            cmd += ["-b:a", f"{kbps}k"]

        cmd += ["-f", "mp3", "pipe:1"]

        try:
            proc = subprocess.run(
                cmd,
                input=raw_pcm,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            return proc.stdout if proc.stdout else None
        except Exception:
            return None

    def _export_optimized_mp3(self, audio_data: bytes) -> bytes:
        """Exporte l'audio en MP3 avec compression optimisée pour réduire la taille."""
        logger = logging.getLogger(__name__)
        sample_rate = self.AUDIO_CONFIG["sample_rate"]
        # Le mix produit du PCM s16le, 2 octets/échantillon
        # Adaptez 'channels' si votre mix final est mono ou stéréo
        channels = self.AUDIO_CONFIG.get("ffmpeg_channels", 1)

        # 1) ffmpeg (prioritaire)
        mp3_data = self._encode_mp3_ffmpeg(audio_data, sample_rate, channels)
        if mp3_data:
            logger.info(f"🎵 ffmpeg MP3: {len(audio_data)} -> {len(mp3_data)} bytes")
            return mp3_data

        # 2) pydub (fallback)
        try:
            import io
            from pydub import AudioSegment

            audio_segment = AudioSegment(
                audio_data,
                frame_rate=sample_rate,
                sample_width=2,     # s16le
                channels=channels
            )
            buf = io.BytesIO()
            audio_segment.export(
                buf,
                format="mp3",
                bitrate=f"{self.AUDIO_CONFIG['mp3_bitrate']}k",
            )
            mp3_data = buf.getvalue()
            logger.info(f"🎵 pydub MP3: {len(audio_data)} -> {len(mp3_data)} bytes")
            return mp3_data
        except Exception as e:
            logger.warning(f"⚠️ Fallback pydub échoué: {e}")

        # 3) Dernier recours: brut
        logger.warning("⚠️ Aucun encodeur MP3 dispo, retour des données brutes")
        return audio_data
