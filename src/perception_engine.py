"""
Perception engine — VAD-based recording, screen capture, optional vision.

Wraps microphone listening with voice activity detection so recordings
are variable-length (user speaks until they stop), not fixed 5-second clips.
"""

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd


@dataclass
class RecordingResult:
    audio: np.ndarray
    sample_rate: int
    duration_sec: float


class PerceptionEngine:
    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.003,
        silence_timeout_sec: float = 1.5,
        max_record_sec: float = 30.0,
        min_record_sec: float = 0.5,
    ):
        self._sample_rate = sample_rate
        self._energy_threshold = energy_threshold
        self._silence_timeout = silence_timeout_sec
        self._max_record = max_record_sec
        self._min_record = min_record_sec
        self._frame_duration_ms = 30
        self._frame_size = int(sample_rate * self._frame_duration_ms / 1000)
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._running = False

    # ------------------------------------------------------------------
    # Recording with VAD
    # ------------------------------------------------------------------

    def record_until_silence(self) -> Optional[RecordingResult]:
        """Record audio until the user stops speaking (silence timeout)."""
        self._running = True
        recording: list[np.ndarray] = []
        silence_frames = 0
        speech_frames = 0
        silence_limit = int(self._silence_timeout / (self._frame_duration_ms / 1000))
        max_frames = int(self._max_record / (self._frame_duration_ms / 1000))
        started = False

        try:
            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                blocksize=self._frame_size,
                callback=self._callback,
            ):
                while self._running and len(recording) < max_frames:
                    try:
                        chunk = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    rms = np.sqrt(np.mean(chunk ** 2))
                    is_speech = rms > self._energy_threshold

                    if is_speech:
                        speech_frames += 1
                        silence_frames = 0
                        if speech_frames > 3 and not started:
                            started = True
                    else:
                        silence_frames += 1
                        if started:
                            speech_frames = max(0, speech_frames - 1)

                    recording.append(chunk)

                    if started and silence_frames > silence_limit:
                        break

            if not started or len(recording) < int(self._min_record / (self._frame_duration_ms / 1000)):
                return None

            audio = np.concatenate(recording)
            duration = len(audio) / self._sample_rate
            return RecordingResult(audio=audio, sample_rate=self._sample_rate, duration_sec=duration)

        except Exception as e:
            print(f"[Perception] Record error: {e}")
            return None
        finally:
            self._running = False

    @staticmethod
    def calibrate(duration_sec: float = 2.0) -> float:
        """Measure ambient noise and suggest an energy_threshold.

        Records for `duration_sec` seconds (you should speak for the
        second half), then returns a threshold ~2x the quiet RMS.
        """
        import sounddevice as sd
        sr = 16000
        print(f"[Calibrate] Recording for {duration_sec}s — {'stay silent first half, then speak' if duration_sec > 1 else 'speak now'}...")
        rec = sd.rec(int(duration_sec * sr), samplerate=sr, channels=1, dtype=np.float32)
        sd.wait()
        # Use the last half (or all if short) to detect speech level
        half = len(rec) // 2
        levels = [np.sqrt(np.mean(rec[i:i+sr//10] ** 2)) for i in range(0, len(rec), sr//10)]
        quiet = sorted(levels)[:len(levels)//3]  # bottom third = noise floor
        noise_floor = np.mean(quiet) if quiet else 0.001
        suggested = max(noise_floor * 3, 0.002)
        print(f"[Calibrate] Noise floor: {noise_floor:.5f}")
        print(f"[Calibrate] Suggested energy_threshold: {suggested:.5f}")
        return suggested

    def _callback(self, indata, frames, time_info, status):
        mono = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
        self._audio_queue.put(mono)

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
