"""
Activation: Energy-based VAD + Whisper wake word detection, with hotkey.

No API keys, no extra dependencies beyond what's already installed.
Uses RMS energy threshold to detect speech, then Whisper for wake word.
"""

import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


class ActivationEngine:
    def __init__(
        self,
        wake_word: str = "computer",
        hotkey: str = "ctrl+space",
        sample_rate: int = 16000,
        energy_threshold: float = 0.02,
        min_speech_frames: int = 15,
    ):
        self._wake_word = wake_word.lower()
        self._hotkey = hotkey
        self._sample_rate = sample_rate
        self._energy_threshold = energy_threshold
        self._min_speech_frames = min_speech_frames
        self._frame_size = int(sample_rate * 0.03)  # 30ms frames
        self._running = False
        self._listening = False
        self._on_activate: Optional[Callable[[], None]] = None
        self._on_deactivate: Optional[Callable[[], None]] = None
        self._hotkey_handler = None

        # Whisper tiny for wake word detection (fast, ~1.5GB RAM, reuses cached model)
        self._ww_model = WhisperModel("tiny", device="auto", compute_type="int8")

        # Ring buffer: keep last 3 seconds of audio
        self._ring_size = 3 * sample_rate
        self._ring = np.zeros(self._ring_size, dtype=np.float32)
        self._ring_pos = 0
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        self._running = True
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        self._start_hotkey()
        print(f"[WakeWord] Listening for '{self._wake_word}' + hotkey '{self._hotkey}'")

    def stop(self):
        self._running = False
        self._stop_hotkey()

    @property
    def is_listening(self) -> bool:
        return self._listening

    def on_activate(self, callback: Callable[[], None]):
        self._on_activate = callback

    def on_deactivate(self, callback: Callable[[], None]):
        self._on_deactivate = callback

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _activate(self):
        if not self._listening:
            self._listening = True
            if self._on_activate:
                self._on_activate()

    def _deactivate(self):
        if self._listening:
            self._listening = False
            if self._on_deactivate:
                self._on_deactivate()

    def _toggle(self):
        if self._listening:
            self._deactivate()
        else:
            self._activate()

    def _start_hotkey(self):
        import keyboard as kb
        self._hotkey_handler = kb.add_hotkey(self._hotkey, self._toggle)

    def _stop_hotkey(self):
        if self._hotkey_handler is not None:
            import keyboard as kb
            kb.remove_hotkey(self._hotkey_handler)

    def _audio_callback(self, indata, frames, time_info, status):
        mono = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
        n = len(mono)
        if self._ring_pos + n <= self._ring_size:
            self._ring[self._ring_pos:self._ring_pos + n] = mono
        else:
            part = self._ring_size - self._ring_pos
            self._ring[self._ring_pos:] = mono[:part]
            self._ring[:n - part] = mono[part:]
        self._ring_pos = (self._ring_pos + n) % self._ring_size
        self._audio_queue.put(mono)

    def _run(self):
        stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            blocksize=self._frame_size,
            callback=self._audio_callback,
        )
        stream.start()

        speech_count = 0
        try:
            while self._running:
                try:
                    chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Energy-based VAD
                rms = np.sqrt(np.mean(chunk ** 2))
                if rms > self._energy_threshold:
                    speech_count += 1
                else:
                    speech_count = max(0, speech_count - 2)

                # Check for wake word after sustained speech
                if speech_count >= self._min_speech_frames and not self._listening:
                    speech_count = 0
                    self._check_wake_word()
        finally:
            stream.stop()
            stream.close()

    def _check_wake_word(self):
        segments, _ = self._ww_model.transcribe(self._ring, beam_size=1, language="en")
        text = " ".join(seg.text for seg in segments).strip().lower()
        if text and self._wake_word in text:
            print(f"[WakeWord] Detected '{self._wake_word}'")
            self._activate()
