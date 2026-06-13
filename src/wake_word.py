"""
Activation: Energy-based VAD + Whisper wake word detection, with hotkey.

Uses sd.rec() polling loop instead of InputStream callback because
some devices (WDM-KS) don't support callback mode in PortAudio.
"""

import queue
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from src.mic_utils import find_best_device, resample_to_16k, convert_to_float


class ActivationEngine:
    def __init__(
        self,
        wake_word: str = "computer",
        hotkey: str = "ctrl+space",
        sample_rate: int = 16000,
        energy_threshold: float = 0.04,
        min_speech_frames: int = 8,
    ):
        self._wake_word = wake_word.lower()
        self._hotkey = hotkey
        self._target_sr = sample_rate
        self._energy_threshold = energy_threshold
        self._min_speech_frames = min_speech_frames

        # Auto-detect best mic
        mic = find_best_device()
        self._device = mic["index"]
        self._device_sr = mic["samplerate"]
        self._device_dtype = mic["dtype"]
        self._frame_ms = 50  # 50ms chunks for polling
        self._frame_size = int(self._device_sr * self._frame_ms / 1000)

        self._running = False
        self._listening = False
        self._on_activate: Optional[Callable[[], None]] = None
        self._on_deactivate: Optional[Callable[[], None]] = None
        self._hotkey_handler = None

        # Whisper tiny for wake word detection
        self._ww_model = WhisperModel("tiny", device="auto", compute_type="int8")

        # Ring buffer: keep last 3 seconds of audio at target SR
        self._ring = np.zeros(3 * self._target_sr, dtype=np.float32)
        self._ring_pos = 0

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
            print("[WakeWord] Activated", flush=True)
            if self._on_activate:
                self._on_activate()

    def _deactivate(self):
        if self._listening:
            self._listening = False
            print("[WakeWord] Deactivated", flush=True)
            if self._on_deactivate:
                self._on_deactivate()

    def _toggle(self):
        print("[WakeWord] Hotkey toggled", flush=True)
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

    def _add_to_ring(self, audio: np.ndarray):
        """Add float32 audio at target SR to the ring buffer."""
        n = len(audio)
        if self._ring_pos + n <= len(self._ring):
            self._ring[self._ring_pos:self._ring_pos + n] = audio
        else:
            part = len(self._ring) - self._ring_pos
            self._ring[self._ring_pos:] = audio[:part]
            self._ring[:n - part] = audio[part:]
        self._ring_pos = (self._ring_pos + n) % len(self._ring)

    def _run(self):
        speech_count = 0
        consecutive_silence = 0
        warmup_frames = 20  # discard first ~1s of audio (device init burst)

        while self._running:
            # Yield mic to perception engine while listening
            if self._listening:
                time.sleep(0.05)
                continue

            # Warmup: discard first frames to avoid device init noise
            if warmup_frames > 0:
                try:
                    sd.rec(self._frame_size, samplerate=self._device_sr,
                           channels=1, dtype=self._device_dtype, device=self._device)
                    sd.wait()
                except Exception:
                    pass
                warmup_frames -= 1
                continue

            try:
                chunk = sd.rec(self._frame_size, samplerate=self._device_sr,
                               channels=1, dtype=self._device_dtype, device=self._device)
                sd.wait()
                chunk = chunk.flatten()
            except Exception as e:
                time.sleep(0.05)
                continue

            # Convert to float32 and downsample to 16k
            audio = convert_to_float(chunk, self._device_dtype)
            if self._device_sr != self._target_sr:
                audio = resample_to_16k(audio, self._device_sr)

            # Update ring buffer with 16k audio
            self._add_to_ring(audio)

            # Energy-based VAD
            rms = np.sqrt(np.mean(audio ** 2))
            if rms > self._energy_threshold:
                speech_count += 1
                consecutive_silence = 0
            else:
                speech_count = max(0, speech_count - 2)
                consecutive_silence += 1

            # Check for wake word after sustained speech
            if speech_count >= self._min_speech_frames and not self._listening:
                speech_count = 0
                self._check_wake_word()

    def _check_wake_word(self):
        segments, _ = self._ww_model.transcribe(self._ring, beam_size=1, language="en")
        text = " ".join(seg.text for seg in segments).strip().lower()
        print(f"[WakeWord] Ring transcribed: '{text}'", flush=True)
        if text and self._wake_word in text:
            print(f"[WakeWord] Detected '{self._wake_word}'")
            self._activate()
