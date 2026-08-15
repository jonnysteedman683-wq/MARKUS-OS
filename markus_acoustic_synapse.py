#!/usr/bin/env python3
"""
MARKUS OS Acoustic Synapse Resonance Generator & Neural Synthesis Matrix (Upgrade 26)
Generates procedural harmonic audio, neural entrainment frequencies (Delta, Theta, Alpha, Beta, Gamma),
and acoustic feedback profiles directly from kernel events and state transitions.
Outputs pure PCM/WAV byte streams (stdlib only) and Web Audio JSON synthesis matrices.
"""

from __future__ import annotations
import base64
import io
import json
import logging
import math
import struct
import time
import wave
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Markus.AcousticSynapse")

# Neural frequency bands (Hz)
NEURAL_BANDS = {
    "DELTA": {"min": 0.5, "max": 4.0, "center": 2.5, "state": "DEEP_CORTEX_IDLE"},
    "THETA": {"min": 4.0, "max": 8.0, "center": 6.0, "state": "MEMORY_CONSOLIDATION"},
    "ALPHA": {"min": 8.0, "max": 13.0, "center": 10.5, "state": "ATTENTIVE_READINESS"},
    "BETA":  {"min": 13.0, "max": 30.0, "center": 20.0, "state": "ACTIVE_REASONING"},
    "GAMMA": {"min": 30.0, "max": 100.0, "center": 40.0, "state": "HYPER_CONSENSUS_CONVERGENCE"}
}

# Synaptic harmonic resonance chord presets
HARMONIC_PRESETS: Dict[str, Dict[str, Any]] = {
    "KERNEL_BOOT": {
        "frequencies": [261.63, 329.63, 392.00, 523.25],  # C Major
        "duration_s": 0.35,
        "waveform": "sine",
        "description": "Kernel initialization chime"
    },
    "INTENT_DISPATCH": {
        "frequencies": [440.00, 554.37, 659.25, 880.00],  # A Major
        "duration_s": 0.18,
        "waveform": "sine",
        "description": "Intent dispatched to multi-model router"
    },
    "CONSENSUS_SUCCESS": {
        "frequencies": [523.25, 659.25, 783.99, 1046.50], # C Major Pentatonic
        "duration_s": 0.25,
        "waveform": "triangle",
        "description": "Multi-model consensus verified and committed"
    },
    "FAULT_DISSONANCE": {
        "frequencies": [185.00, 261.63, 369.99],          # Tritone Dissonance
        "duration_s": 0.30,
        "waveform": "sawtooth",
        "description": "Circuit-breaker trip or execution fault"
    },
    "DICE_PENTATONIC": {
        "frequencies": [587.33, 659.25, 783.99, 880.00, 1046.50],
        "duration_s": 0.20,
        "waveform": "sine",
        "description": "Dice Engine roll sequence sweep"
    },
    "DAG_STEP_RESONANCE": {
        "frequencies": [392.00, 493.88, 587.33, 783.99],  # G Major 7th
        "duration_s": 0.15,
        "waveform": "sine",
        "description": "Task DAG node completed"
    }
}

@dataclass
class AudioSynthesisResult:
    preset_name: str
    sample_rate: int
    duration_s: float
    frequencies: List[float]
    wav_bytes_base64: str
    raw_byte_length: int
    web_audio_matrix: Dict[str, Any]
    elapsed_ms: float

class MarkusAcousticSynapse:
    """
    Synthesizes pure procedural audio frames (16-bit PCM WAV) and Web Audio parameters
    representing system states, thought emissions, and model dispatch events.
    """

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate

    def generate_wav_bytes(
        self,
        frequencies: List[float],
        duration_s: float = 0.2,
        waveform: str = "sine",
        volume: float = 0.4
    ) -> bytes:
        """Generates standard 16-bit Mono WAV audio buffer in memory."""
        total_samples = int(self.sample_rate * duration_s)
        out_bytes = io.BytesIO()

        with wave.open(out_bytes, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit PCM
            wav_file.setframerate(self.sample_rate)

            frames = bytearray()
            num_freqs = max(1, len(frequencies))

            for i in range(total_samples):
                t = i / self.sample_rate
                # Exponential decay envelope
                envelope = math.exp(-3.5 * (t / duration_s))

                sample_val = 0.0
                for freq in frequencies:
                    if waveform == "sine":
                        sample_val += math.sin(2.0 * math.pi * freq * t)
                    elif waveform == "triangle":
                        # Normalized triangle wave (-1.0 to 1.0)
                        sample_val += 2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0
                    elif waveform == "sawtooth":
                        sample_val += 2.0 * (t * freq - math.floor(t * freq + 0.5))
                    else:
                        sample_val += math.sin(2.0 * math.pi * freq * t)

                sample_val = (sample_val / num_freqs) * volume * envelope
                sample_val = max(-1.0, min(1.0, sample_val))
                int_sample = int(sample_val * 32767.0)
                frames.extend(struct.pack("<h", int_sample))

            wav_file.writeframes(frames)

        return out_bytes.getvalue()

    def synthesize_preset(self, preset_name: str) -> AudioSynthesisResult:
        """Synthesizes an audio profile from harmonic presets."""
        t0 = time.perf_counter()
        preset = HARMONIC_PRESETS.get(preset_name, HARMONIC_PRESETS["INTENT_DISPATCH"])

        freqs = preset["frequencies"]
        dur = preset["duration_s"]
        wave_type = preset.get("waveform", "sine")

        wav_data = self.generate_wav_bytes(
            frequencies=freqs,
            duration_s=dur,
            waveform=wave_type
        )

        b64_str = base64.b64encode(wav_data).decode("ascii")
        t1 = time.perf_counter()

        web_audio = {
            "preset": preset_name,
            "waveform": wave_type,
            "duration": dur,
            "frequencies": freqs,
            "chords": [{"freq": f, "gain": round(0.1 / len(freqs), 3)} for f in freqs]
        }

        return AudioSynthesisResult(
            preset_name=preset_name,
            sample_rate=self.sample_rate,
            duration_s=dur,
            frequencies=freqs,
            wav_bytes_base64=b64_str,
            raw_byte_length=len(wav_data),
            web_audio_matrix=web_audio,
            elapsed_ms=round((t1 - t0) * 1000, 2)
        )

    def get_neural_matrix(self) -> Dict[str, Any]:
        """Returns neural frequency bands and resonance mapping."""
        return {
            "neural_bands": NEURAL_BANDS,
            "harmonic_presets": {
                k: {
                    "frequencies": v["frequencies"],
                    "duration_s": v["duration_s"],
                    "waveform": v["waveform"],
                    "description": v["description"]
                }
                for k, v in HARMONIC_PRESETS.items()
            }
        }

def _test_acoustic_synapse():
    print("=== MARKUS Acoustic Synapse Resonance Subsystem Test ===")
    syn = MarkusAcousticSynapse(sample_rate=22050)

    for preset_name in HARMONIC_PRESETS:
        res = syn.synthesize_preset(preset_name)
        print(f"  [PASS] Synthesized '{preset_name.ljust(20)}' WAV={res.raw_byte_length} bytes  Latency={res.elapsed_ms:.2f}ms")
        assert res.raw_byte_length > 44, "WAV header missing or incomplete"
        assert len(res.wav_bytes_base64) > 0, "Base64 encoding empty"

    matrix = syn.get_neural_matrix()
    assert "DELTA" in matrix["neural_bands"], "Neural bands missing DELTA"
    assert "CONSENSUS_SUCCESS" in matrix["harmonic_presets"], "Presets missing CONSENSUS_SUCCESS"
    print("\n✅ Acoustic Synapse Resonance Generator: PASSED")

if __name__ == "__main__":
    _test_acoustic_synapse()
