"""
Speech-to-text engine using faster-whisper (local).
"""

import numpy as np
from faster_whisper import WhisperModel


class STTEngine:
    def __init__(self, model_size: str = "base", device: str = "auto"):
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        segments, _ = self._model.transcribe(audio_data, beam_size=1, language="en")
        return " ".join(seg.text for seg in segments).strip()

    def transcribe_file(self, path: str) -> str:
        segments, _ = self._model.transcribe(path, beam_size=1, language="en")
        return " ".join(seg.text for seg in segments).strip()
