"""Pipeline de génération de podcasts de type wellness."""

import logging
import subprocess
import tempfile
import shutil
from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from .base_pipeline import BasePipeline
from app.prompts import load_tts_prompt

logger = logging.getLogger(__name__)


class WellnessPipeline(BasePipeline):
    """Pipeline spécialisé pour les podcasts de type wellness/méditation."""
    
    # Configuration audio optimisée pour 16kHz mono
    AUDIO_CONFIG = {
        "sample_rate": 16000,     # 16kHz mono pour TTS et podcast
        "background_volume": 0.1,  # 10% du volume pour le bruit de fond
        "tts_volume_boost": 1.0,   # Pas de boost, volume normal
        "save_wav": False,         # Désactive WAV (gros gain)
        "save_mp3": True,
        "mp3_bitrate": 32,         # Bitrate réduit pour 16kHz mono
        # Options ffmpeg pour 16kHz mono
        "ffmpeg_enable": True,     # Utilise ffmpeg pour tout le traitement
        "ffmpeg_channels": 1,      # mono uniquement
        "ffmpeg_vbr_q": 4,         # VBR qualité 4 pour 16kHz mono (~32kbps)
        "ffmpeg_cbr_kbps": 32,     # CBR 32kbps pour 16kHz mono
        "ffmpeg_use_vbr": True     # True pour VBR, False pour CBR
    }
    
    # Réglage du volume du bruit de fond (0.0 = silence, 1.0 = volume normal)
    BACKGROUND_VOLUME = 0.1  # 10% du volume pour le bruit de fond
    
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
            # Charger le bruit de fond theta_wave.wav
            theta_wave_path = Path(__file__).parent.parent.parent / "theta_wave.wav"
            if not theta_wave_path.exists():
                raise FileNotFoundError(f"Fichier theta_wave.wav non trouvé: {theta_wave_path}")
            
            logger.info("🎵 Chargement du bruit de fond theta_wave.wav...")
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
                            "duration": len(audio_bytes) / 32000,  # Estimation pour 16kHz mono (16-bit)
                            "type": "speech",
                            "category": category
                        })
                        total_duration += len(audio_bytes) / 32000
                    
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
            # Estimation basique : 1 seconde pour 32KB (16kHz mono, 16-bit)
            return len(audio_bytes) // 32000

    async def _assemble_wellness_audio(
        self, 
        segments: List[Dict], 
        theta_wave_bytes: bytes, 
        total_duration: float
    ) -> bytes:
        """Assemble l'audio final avec bruit de fond et pauses respectées en utilisant ffmpeg."""
        try:
            import tempfile
            import subprocess
            import shutil
            import os
            
            logger = logging.getLogger(__name__)
            
            logger.info("🎵 Assemblage audio avec ffmpeg (16kHz mono)")
            
            # Vérifier que ffmpeg est disponible
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                raise RuntimeError("ffmpeg non trouvé, impossible de traiter l'audio")
            
            # Créer des fichiers temporaires
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                
                # 1. Sauvegarder le bruit de fond theta
                theta_path = temp_dir / "theta_wave.wav"
                with open(theta_path, 'wb') as f:
                    f.write(theta_wave_bytes)
                
                # 2. Convertir le bruit de fond en 16kHz mono
                theta_16k_path = temp_dir / "theta_16k.wav"
                self._convert_to_16k_mono(ffmpeg_path, theta_path, theta_16k_path)
                
                # 3. Créer un fichier de silence pour les pauses
                silence_path = temp_dir / "silence.wav"
                self._create_silence(ffmpeg_path, silence_path, 1.0)  # 1 seconde de silence
                
                # 4. Traiter chaque segment TTS et les convertir en 16kHz mono
                speech_files = []
                current_time = 60.0  # Commencer 60 secondes après le début
                
                for segment in segments:
                    if segment["type"] == "speech" and segment["audio"]:
                        # Sauvegarder le segment TTS
                        speech_path = temp_dir / f"speech_{len(speech_files)}.wav"
                        with open(speech_path, 'wb') as f:
                            f.write(segment["audio"])
                        
                        # Convertir en 16kHz mono
                        speech_16k_path = temp_dir / f"speech_16k_{len(speech_files)}.wav"
                        self._convert_to_16k_mono(ffmpeg_path, speech_path, speech_16k_path)
                        
                        # Appliquer le volume de la voix
                        speech_vol_path = temp_dir / f"speech_vol_{len(speech_files)}.wav"
                        self._apply_volume(ffmpeg_path, speech_16k_path, speech_vol_path, 1.0)
                        
                        speech_files.append({
                            "file": speech_vol_path,
                            "start_time": current_time,
                            "duration": self._get_audio_duration(speech_vol_path)
                        })
                        
                        current_time += self._get_audio_duration(speech_vol_path)
                        logger.debug(f"   Ajouté: {segment['category']} à {current_time:.1f}s")
                    
                    elif segment["type"] == "silence":
                        # Ajouter du silence (garder le bruit de fond)
                        silence_duration = segment.get("duration", 0)
                        current_time += silence_duration
                        logger.debug(f"  ⏸️ Silence: {silence_duration}s à {current_time:.1f}s")
                    
                    # Gérer les pauses après chaque segment
                    pause_duration = segment.get("pause_after_sec", 0)
                    if pause_duration > 0:
                        current_time += pause_duration
                        logger.debug(f"  ⏸️ Pause: {pause_duration}s à {current_time:.1f}s")
                
                # 5. Créer le fichier de voix final
                voice_path = temp_dir / "voice_final.wav"
                self._create_voice_track(ffmpeg_path, speech_files, voice_path, current_time + 60)
                
                # 6. Appliquer le volume au bruit de fond
                theta_vol_path = temp_dir / "theta_vol.wav"
                background_vol = self.AUDIO_CONFIG["background_volume"]
                self._apply_volume(ffmpeg_path, theta_16k_path, theta_vol_path, background_vol)
                
                # 7. Mélanger la voix et le bruit de fond
                final_path = temp_dir / "final.wav"
                self._mix_audio(ffmpeg_path, voice_path, theta_vol_path, final_path)
                
                # 8. Lire le résultat final
                with open(final_path, 'rb') as f:
                    final_audio = f.read()
                
                logger.info(f"✅ Audio final assemblé avec ffmpeg: {len(final_audio)} bytes")
                return final_audio
                
        except Exception as e:
            logger.error(f"Erreur assemblage audio wellness: {e}")
            raise
    
    def _convert_to_16k_mono(self, ffmpeg_path: str, input_path: Path, output_path: Path):
        """Convertit un fichier audio en 16kHz mono avec ffmpeg."""
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-ar", "16000",  # 16kHz
            "-ac", "1",      # mono
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-y",  # Overwrite output
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"✅ Converti en 16kHz mono: {input_path.name} -> {output_path.name}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur conversion 16kHz mono: {e.stderr.decode()}")
            raise
    
    def _create_silence(self, ffmpeg_path: str, output_path: Path, duration: float):
        """Crée un fichier de silence de durée donnée."""
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=mono:sample_rate=16000",
            "-t", str(duration),
            "-acodec", "pcm_s16le",
            "-y",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"✅ Silence créé: {duration}s")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur création silence: {e.stderr.decode()}")
            raise
    
    def _apply_volume(self, ffmpeg_path: str, input_path: Path, output_path: Path, volume: float):
        """Applique un facteur de volume à un fichier audio."""
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-i", str(input_path),
            "-filter:a", f"volume={volume}",
            "-acodec", "pcm_s16le",
            "-y",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug(f"✅ Volume appliqué: {volume}x")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur application volume: {e.stderr.decode()}")
            raise
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """Obtient la durée d'un fichier audio en secondes."""
        try:
            from mutagen.wave import WAVE
            audio_file = WAVE(str(audio_path))
            duration = audio_file.info.length
            logger.debug(f"Durée audio: {duration:.2f}s")
            return duration
        except Exception as e:
            logger.warning(f"Impossible de calculer la durée: {e}")
            return 1.0  # Durée par défaut
    
    def _create_voice_track(self, ffmpeg_path: str, speech_files: List[Dict], output_path: Path, total_duration: float):
        """Crée la piste de voix finale avec les segments positionnés correctement."""
        if not speech_files:
            # Créer un fichier de silence si pas de segments
            self._create_silence(ffmpeg_path, output_path, total_duration)
            return
        
        # Créer un fichier de silence de la durée totale
        silence_path = output_path.parent / "temp_silence.wav"
        self._create_silence(ffmpeg_path, silence_path, total_duration)
        
        try:
            # Approche simplifiée : concaténer les segments de voix
            if len(speech_files) == 1:
                # Un seul segment, le copier directement
                import shutil
                shutil.copy2(speech_files[0]["file"], output_path)
            else:
                # Plusieurs segments, les concaténer
                cmd = [ffmpeg_path, "-hide_banner", "-loglevel", "error"]
                
                # Ajouter tous les fichiers de voix
                for speech_file in speech_files:
                    cmd.extend(["-i", str(speech_file["file"])])
                
                # Concaténer simplement
                cmd.extend(["-filter_complex", f"concat=n={len(speech_files)}:v=0:a=1[out]"])
                cmd.extend(["-map", "[out]", "-acodec", "pcm_s16le", "-y", str(output_path)])
                
                subprocess.run(cmd, check=True, capture_output=True)
            
            logger.debug(f"✅ Piste de voix créée: {len(speech_files)} segments")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur création piste voix: {e.stderr.decode()}")
            # Fallback: copier le silence
            import shutil
            shutil.copy2(silence_path, output_path)
        finally:
            # Nettoyer le fichier temporaire
            if silence_path.exists():
                silence_path.unlink()
    
    def _mix_audio(self, ffmpeg_path: str, voice_path: Path, background_path: Path, output_path: Path):
        """Mélange la voix et le bruit de fond."""
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-i", str(voice_path),
            "-i", str(background_path),
            "-filter_complex", "[0][1]amix=inputs=2:duration=first:weights=1 1:dropout_transition=0",
            "-acodec", "pcm_s16le",
            "-y",
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.debug("✅ Audio mélangé avec succès")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur mélange audio: {e.stderr.decode()}")
            raise
    
    def _encode_mp3_ffmpeg(self, raw_pcm: bytes, sample_rate: int, channels: int) -> Optional[bytes]:
        import shutil, subprocess

        if not self.AUDIO_CONFIG.get("ffmpeg_enable", True):
            return None

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            return None

        # Préparer commande ffmpeg: entrée PCM s16le (little-endian), sortie MP3 16kHz mono
        cmd = [
            ffmpeg_path,
            "-hide_banner", "-loglevel", "error",
            "-f", "s16le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-i", "pipe:0",
            "-vn",
            "-ac", "1",  # Force mono
            "-ar", "16000",  # Force 16kHz
        ]

        if self.AUDIO_CONFIG.get("ffmpeg_use_vbr", True):
            # VBR: qualité perceptuelle meilleure à taille équivalente
            q = int(self.AUDIO_CONFIG.get("ffmpeg_vbr_q", 4))
            cmd += ["-q:a", str(q)]
        else:
            # CBR
            kbps = int(self.AUDIO_CONFIG.get("ffmpeg_cbr_kbps", 32))
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
        """Exporte l'audio en MP3 avec compression optimisée pour 16kHz mono."""
        logger = logging.getLogger(__name__)
        sample_rate = self.AUDIO_CONFIG["sample_rate"]  # 16000
        channels = 1  # Force mono

        # 1) ffmpeg (prioritaire)
        mp3_data = self._encode_mp3_ffmpeg(audio_data, sample_rate, channels)
        if mp3_data:
            logger.info(f"🎵 ffmpeg MP3 16kHz mono: {len(audio_data)} -> {len(mp3_data)} bytes")
            return mp3_data

        # 2) pydub (fallback)
        try:
            import io
            from pydub import AudioSegment

            audio_segment = AudioSegment(
                audio_data,
                frame_rate=sample_rate,
                sample_width=2,     # s16le
                channels=channels   # mono
            )
            buf = io.BytesIO()
            audio_segment.export(
                buf,
                format="mp3",
                bitrate=f"{self.AUDIO_CONFIG['mp3_bitrate']}k",
            )
            mp3_data = buf.getvalue()
            logger.info(f"🎵 pydub MP3 16kHz mono: {len(audio_data)} -> {len(mp3_data)} bytes")
            return mp3_data
        except Exception as e:
            logger.warning(f"⚠️ Fallback pydub échoué: {e}")

        # 3) Dernier recours: brut
        logger.warning("⚠️ Aucun encodeur MP3 dispo, retour des données brutes")
        return audio_data
