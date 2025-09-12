"""Système de mastering audio pour podcasts."""

import io
import logging
from typing import List, Dict, Any
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
from pydub.generators import WhiteNoise

logger = logging.getLogger(__name__)


class AudioMastering:
    """Système de mastering audio pour podcasts avec filtres broadcast."""
    
    def __init__(self):
        self.target_lufs_mono = -19.0
        self.target_lufs_stereo = -16.0
        self.true_peak_limit = -1.0
        
    def master_audio(self, segments: List[Dict[str, Any]]) -> bytes:
        """Applique le mastering complet sur les segments audio."""
        try:
            logger.info("🎛️ Début du mastering audio")
            
            # 1. Charger et normaliser chaque segment
            processed_segments = []
            for i, seg in enumerate(segments):
                if not seg.get("audio"):
                    continue
                    
                audio_seg = self._load_audio_segment(seg["audio"])
                if audio_seg is None:
                    continue
                    
                # Normalisation par segment
                normalized = self._normalize_segment(audio_seg)
                processed_segments.append(normalized)
                logger.debug(f"Segment {i} normalisé: {len(normalized)}ms")
            
            if not processed_segments:
                raise ValueError("Aucun segment audio valide")
            
            logger.info(f"🎛️ {len(processed_segments)} segments à traiter")
            
            # 2. Concaténer avec fades
            master_audio = self._concatenate_with_fades(processed_segments)
            logger.debug("🎛️ Concaténation avec fades terminée")
            
            # 3. Appliquer l'égalisation
            eq_audio = self._apply_eq(master_audio)
            logger.debug("🎛️ Égalisation appliquée")
            
            # 4. Compression dynamique
            compressed = self._apply_compression(eq_audio)
            logger.debug("🎛️ Compression dynamique appliquée")
            
            # 5. De-esser et filtres
            filtered = self._apply_filters(compressed)
            logger.debug("🎛️ Filtres de post-traitement appliqués")
            
            # 6. Normalisation finale et limiting
            final_audio = self._final_normalization(filtered)
            logger.debug("🎛️ Normalisation finale terminée")
            
            # 7. Export WAV final (haute qualité)
            wav_result = self._export_wav(final_audio)
            logger.info(f"🎛️ Mastering WAV terminé: {len(wav_result)} bytes")
            
            # 8. Conversion finale en MP3 avec ffmpeg
            mp3_result = self._convert_to_mp3_ffmpeg(wav_result)
            if mp3_result:
                logger.info(f"🎛️ Conversion MP3 terminée: {len(mp3_result)} bytes")
                return mp3_result
            else:
                logger.warning("⚠️ Conversion MP3 échouée, retour du WAV")
                return wav_result
            
        except Exception as e:
            logger.error(f"Erreur mastering audio: {e}")
            # Fallback: concaténation simple
            return self._fallback_concat(segments)
    
    def _load_audio_segment(self, audio_bytes: bytes) -> AudioSegment:
        """Charge un segment audio depuis des bytes WAV."""
        try:
            return AudioSegment.from_wav(io.BytesIO(audio_bytes))
        except Exception as e:
            logger.warning(f"Impossible de charger segment audio WAV: {e}")
            # Fallback: essayer MP3 si WAV échoue
            try:
                return AudioSegment.from_mp3(io.BytesIO(audio_bytes))
            except Exception as e2:
                logger.warning(f"Impossible de charger segment audio MP3: {e2}")
                return None
    
    def _normalize_segment(self, audio: AudioSegment) -> AudioSegment:
        """Normalise un segment vers la cible LUFS."""
        # Normalisation simple (pydub ne fait pas de LUFS natif)
        # On utilise une normalisation RMS approximative
        target_db = -20  # Approximation de -19 LUFS
        current_db = audio.dBFS
        if current_db > -60:  # Éviter les segments trop silencieux
            gain_db = target_db - current_db
            # Limiter le gain pour éviter la saturation
            gain_db = min(gain_db, 12)  # Max +12 dB
            return audio.apply_gain(gain_db)
        return audio
    
    def _concatenate_with_fades(self, segments: List[AudioSegment]) -> AudioSegment:
        """Concatène les segments avec des fades pour éviter les clics."""
        if not segments:
            return AudioSegment.silent(1000)
        
        result = segments[0]
        for seg in segments[1:]:
            # Fade out du segment précédent (5-15ms)
            result = result.fade_out(10)
            # Fade in du segment suivant
            seg = seg.fade_in(10)
            result += seg
        
        return result
    
    def _apply_eq(self, audio: AudioSegment) -> AudioSegment:
        """Applique l'égalisation 'son micro'."""
        try:
            # High-pass 70-90 Hz (approximation avec pydub)
            # pydub ne fait pas d'EQ précis, on utilise des filtres basiques
            
            # Filtre passe-haut approximatif (suppression des graves)
            # On réduit les basses fréquences
            filtered = audio.high_pass_filter(80)
            
            # Boost des médiums (2.5-3.5 kHz) - approximation
            # On applique un léger boost dans les hautes fréquences
            boosted = filtered + 1  # +1 dB approximatif
            
            return boosted
        except Exception as e:
            logger.warning(f"EQ échoué, retour audio original: {e}")
            return audio
    
    def _apply_compression(self, audio: AudioSegment) -> AudioSegment:
        """Applique la compression dynamique broadcast."""
        # Compression simple avec pydub
        # Ratio 2:1, seuil -20 dB, attack 15ms, release 100ms
        try:
            return compress_dynamic_range(
                audio, 
                threshold=-20, 
                ratio=2.0, 
                attack=15, 
                release=100
            )
        except Exception as e:
            logger.warning(f"Compression échouée: {e}")
            return audio
    
    def _apply_filters(self, audio: AudioSegment) -> AudioSegment:
        """Applique les filtres de post-traitement."""
        try:
            # De-esser approximatif (réduction 5-8 kHz)
            # On applique un léger filtre passe-bas
            filtered = audio.low_pass_filter(8000)
            
            # Anti-pop (filtre très léger)
            # On applique un fade très court au début
            if len(audio) > 50:
                filtered = filtered.fade_in(5)
            
            return filtered
        except Exception as e:
            logger.warning(f"Filtres échoués, retour audio original: {e}")
            return audio
    
    def _final_normalization(self, audio: AudioSegment) -> AudioSegment:
        """Normalisation finale et limiting."""
        # Normalisation finale
        normalized = normalize(audio)
        
        # Limiting simple (éviter la saturation)
        # On réduit le gain si trop fort
        if normalized.max_dBFS > -1:
            gain_reduction = -1 - normalized.max_dBFS
            normalized = normalized.apply_gain(gain_reduction)
        
        return normalized
    
    def _export_wav(self, audio: AudioSegment) -> bytes:
        """Export WAV optimisé pour mastering (22kHz pour réduire la taille)."""
        # Conversion en mono si nécessaire
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Réduire la fréquence d'échantillonnage pour réduire la taille
        # 22kHz est suffisant pour la parole et réduit la taille de moitié
        audio = audio.set_frame_rate(22050)
        
        # Export WAV 22kHz 16-bit mono (plus petit que 44.1kHz)
        buffer = io.BytesIO()
        audio.export(
            buffer,
            format="wav",
            parameters=["-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1"]
        )
        return buffer.getvalue()
    
    def _convert_to_mp3_ffmpeg(self, wav_bytes: bytes) -> bytes:
        """Convertit WAV en MP3 avec ffmpeg pour qualité optimale."""
        import shutil
        import subprocess
        
        try:
            # Vérifier que ffmpeg est disponible
            ffmpeg_path = shutil.which("ffmpeg")
            if not ffmpeg_path:
                logger.warning("ffmpeg non trouvé, conversion MP3 impossible")
                return None
            
            # Commande ffmpeg pour conversion WAV -> MP3 optimisée podcast
            cmd = [
                ffmpeg_path,
                "-hide_banner", "-loglevel", "error",
                "-f", "wav",
                "-i", "pipe:0",
                "-vn",  # Pas de vidéo
                "-acodec", "libmp3lame",
                "-b:a", "96k",   # Bitrate 96k pour podcast (suffisant pour 22kHz)
                "-ar", "22050",  # Sample rate 22kHz (correspond au WAV)
                "-ac", "1",      # Mono
                "-q:a", "2",     # Qualité VBR
                "-f", "mp3",
                "pipe:1"
            ]
            
            # Exécuter ffmpeg avec timeout pour éviter les blocages
            proc = subprocess.run(
                cmd,
                input=wav_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=30  # Timeout de 30 secondes
            )
            
            if proc.stdout:
                logger.info(f"✅ Conversion ffmpeg WAV->MP3: {len(wav_bytes)} -> {len(proc.stdout)} bytes")
                return proc.stdout
            else:
                logger.warning("ffmpeg n'a produit aucune sortie")
                return None
                
        except subprocess.TimeoutExpired as e:
            logger.error(f"Timeout ffmpeg (30s): {e}")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur ffmpeg: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return None
        except Exception as e:
            logger.error(f"Erreur conversion MP3: {e}")
            return None
    
    def _export_mp3(self, audio: AudioSegment) -> bytes:
        """Export MP3 de fallback avec pydub."""
        # Conversion en mono si nécessaire
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Export MP3 96 kbps mono
        buffer = io.BytesIO()
        audio.export(
            buffer,
            format="mp3",
            bitrate="96k",
            parameters=["-q:a", "2"]  # Qualité VBR
        )
        return buffer.getvalue()
    
    def _fallback_concat(self, segments: List[Dict[str, Any]]) -> bytes:
        """Fallback: concaténation simple sans mastering."""
        logger.warning("Utilisation du fallback de concaténation simple")
        
        # Essayer de charger les segments avec pydub pour une meilleure concaténation
        try:
            from pydub import AudioSegment
            audio_segments = []
            
            for seg in segments:
                if seg.get("audio"):
                    try:
                        # Essayer WAV d'abord
                        audio_seg = AudioSegment.from_wav(io.BytesIO(seg["audio"]))
                        audio_segments.append(audio_seg)
                    except:
                        try:
                            # Fallback MP3
                            audio_seg = AudioSegment.from_mp3(io.BytesIO(seg["audio"]))
                            audio_segments.append(audio_seg)
                        except:
                            logger.warning("Impossible de charger un segment audio")
                            continue
            
            if audio_segments:
                # Concaténer avec pydub
                combined = audio_segments[0]
                for seg in audio_segments[1:]:
                    combined += seg
                
                # Exporter en WAV
                buffer = io.BytesIO()
                combined.export(buffer, format="wav")
                return buffer.getvalue()
        
        except Exception as e:
            logger.warning(f"Fallback pydub échoué: {e}")
        
        # Dernier recours: concaténation brute
        combined = bytearray()
        for seg in segments:
            if seg.get("audio"):
                combined.extend(seg["audio"])
        return bytes(combined)
