"""
Perception engine — VAD-based recording, screen capture, optional vision.

Uses sd.rec() polling loop instead of InputStream callback because
some devices (WDM-KS) don't support callback mode in PortAudio.
"""

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from src.mic_utils import find_best_device, resample_to_16k, convert_to_float


@dataclass
class RecordingResult:
    audio: np.ndarray
    sample_rate: int
    duration_sec: float


class PerceptionEngine:
    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.001,
        silence_timeout_sec: float = 1.5,
        max_record_sec: float = 30.0,
        min_record_sec: float = 0.5,
    ):
        self._target_sr = sample_rate
        self._energy_threshold = energy_threshold
        self._silence_timeout = silence_timeout_sec
        self._max_record = max_record_sec
        self._min_record = min_record_sec
        self._chunk_ms = 100  # 100ms recording chunks

        # Auto-detect best mic
        mic = find_best_device()
        self._device = mic["index"]
        self._device_sr = mic["samplerate"]
        self._device_dtype = mic["dtype"]
        self._chunk_size = int(self._device_sr * self._chunk_ms / 1000)

        self._running = False

    # ------------------------------------------------------------------
    # Recording with VAD
    # ------------------------------------------------------------------

    def record_until_silence(self) -> Optional[RecordingResult]:
        """Record audio until the user stops speaking (silence timeout).

        Uses sd.rec() polling loop to stay compatible with all device APIs.
        """
        self._running = True
        recording: list[np.ndarray] = []
        silence_chunks = 0
        speech_chunks = 0
        silence_limit = int(self._silence_timeout / (self._chunk_ms / 1000))
        max_chunks = int(self._max_record / (self._chunk_ms / 1000))
        min_chunks = int(self._min_record / (self._chunk_ms / 1000))
        started = False

        try:
            for _ in range(max_chunks):
                if not self._running:
                    break

                chunk = sd.rec(self._chunk_size, samplerate=self._device_sr,
                               channels=1, dtype=self._device_dtype, device=self._device)
                sd.wait()
                chunk = chunk.flatten()

                # Convert to float32 and resample to 16k
                audio = convert_to_float(chunk, self._device_dtype)
                if self._device_sr != self._target_sr:
                    audio = resample_to_16k(audio, self._device_sr)

                rms = np.sqrt(np.mean(audio ** 2))
                is_speech = rms > self._energy_threshold

                if is_speech:
                    speech_chunks += 1
                    silence_chunks = 0
                    if speech_chunks > 2 and not started:
                        started = True
                else:
                    silence_chunks += 1
                    if started:
                        speech_chunks = max(0, speech_chunks - 1)

                recording.append(audio)

                if started and silence_chunks > silence_limit:
                    break

            if not started or len(recording) < min_chunks:
                return None

            audio = np.concatenate(recording)
            duration = len(audio) / self._target_sr
            return RecordingResult(audio=audio, sample_rate=self._target_sr, duration_sec=duration)

        except Exception as e:
            print(f"[Perception] Record error: {e}")
            return None
        finally:
            self._running = False

    @staticmethod
    def calibrate(duration_sec: float = 2.0) -> float:
        """Measure ambient noise and suggest an energy_threshold."""
        mic = find_best_device()
        sr = mic["samplerate"]
        dtype = mic["dtype"]
        device = mic["index"]
        print(f"[Calibrate] Recording for {duration_sec}s — speak now...")
        rec = sd.rec(int(duration_sec * sr), samplerate=sr, channels=1, dtype=dtype, device=device)
        sd.wait()
        data = convert_to_float(rec.flatten(), dtype)
        if sr != 16000:
            data = resample_to_16k(data, sr)
        levels = [np.sqrt(np.mean(data[i:i+1600] ** 2)) for i in range(0, len(data), 1600)]
        quiet = sorted(levels)[:len(levels)//3]
        noise_floor = float(np.mean(quiet)) if quiet else 0.001
        suggested = max(noise_floor * 3, 0.002)
        print(f"[Calibrate] Noise floor: {noise_floor:.5f}")
        print(f"[Calibrate] Suggested energy_threshold: {suggested:.5f}")
        return suggested

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------

    @staticmethod
    def capture_screen(save: bool = False) -> Optional[str]:
        """Capture a screenshot. Returns path if saved."""
        try:
            import pyautogui
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = str(Path.home() / "Pictures" / f"jarvis_screen_{ts}.png")
            pyautogui.screenshot(path)
            return path
        except Exception:
            return None

    @staticmethod
    def active_window_title() -> str:
        """Get the title of the currently focused window."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            return active.title if active else ""
        except Exception:
            return ""
