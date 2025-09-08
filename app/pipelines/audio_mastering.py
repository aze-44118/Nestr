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
            
            # 7. Export MP3 optimisé
            result = self._export_mp3(final_audio)
            logger.info(f"🎛️ Mastering terminé: {len(result)} bytes")
            return result
            
        except Exception as e:
            logger.error(f"Erreur mastering audio: {e}")
            # Fallback: concaténation simple
            return self._fallback_concat(segments)
    
    def _load_audio_segment(self, audio_bytes: bytes) -> AudioSegment:
        """Charge un segment audio depuis des bytes MP3."""
        try:
            return AudioSegment.from_mp3(io.BytesIO(audio_bytes))
        except Exception as e:
            logger.warning(f"Impossible de charger segment audio: {e}")
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
        # High-pass 70-90 Hz (approximation avec pydub)
        # pydub ne fait pas d'EQ précis, on utilise des filtres basiques
        
        # Filtre passe-haut approximatif (suppression des graves)
        # On réduit les basses fréquences
        filtered = audio.high_pass_filter(80)
        
        # Boost des médiums (2.5-3.5 kHz) - approximation
        # On applique un léger boost dans les hautes fréquences
        boosted = filtered + 1  # +1 dB approximatif
        
        return boosted
    
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
        # De-esser approximatif (réduction 5-8 kHz)
        # On applique un léger filtre passe-bas
        filtered = audio.low_pass_filter(8000)
        
        # Anti-pop (filtre très léger)
        # On applique un fade très court au début
        if len(audio) > 50:
            filtered = filtered.fade_in(5)
        
        return filtered
    
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
    
    def _export_mp3(self, audio: AudioSegment) -> bytes:
        """Export MP3 optimisé pour podcast."""
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
        combined = bytearray()
        for seg in segments:
            if seg.get("audio"):
                combined.extend(seg["audio"])
        return bytes(combined)
