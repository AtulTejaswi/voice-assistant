"""
Perception engine — VAD-based recording, screen capture, optional vision.

Wraps microphone listening with voice activity detection so recordings
are variable-length (user speaks until they stop), not fixed 5-second clips.
Auto-detects the best microphone device at startup.
"""

import queue
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
        self._frame_duration_ms = 30

        # Auto-detect best mic
        mic = find_best_device()
        self._device = mic["index"]
        self._device_sr = mic["samplerate"]
        self._device_dtype = mic["dtype"]
        self._frame_size = int(self._device_sr * self._frame_duration_ms / 1000)

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stream: Optional[sd.InputStream] = None
        self._running = False

    # ------------------------------------------------------------------
    # Recording with VAD
    # ------------------------------------------------------------------

    def record_until_silence(self) -> Optional[RecordingResult]:
        """Record audio until the user stops speaking (silence timeout).

        Audio is captured at the device's native sample rate, converted
        to float32, and downsampled to the target sample rate (16000).
        """
        self._running = True
        recording: list[np.ndarray] = []
        silence_frames = 0
        speech_frames = 0
        silence_limit = int(self._silence_timeout / (self._frame_duration_ms / 1000))
        max_frames = int(self._max_record / (self._frame_duration_ms / 1000))
        started = False

        try:
            with sd.InputStream(
                samplerate=self._device_sr,
                channels=1,
                blocksize=self._frame_size,
                dtype=self._device_dtype,
                device=self._device,
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
            duration = len(audio) / self._target_sr
            return RecordingResult(audio=audio, sample_rate=self._target_sr, duration_sec=duration)

        except Exception as e:
            print(f"[Perception] Record error: {e}")
            return None
        finally:
            self._running = False

    def _callback(self, indata, frames, time_info, status):
        mono = indata[:, 0] if indata.shape[1] > 1 else indata.flatten()
        mono = convert_to_float(mono, self._device_dtype)
        if self._device_sr != self._target_sr:
            mono = resample_to_16k(mono, self._device_sr)
        self._audio_queue.put(mono)

    @staticmethod
    def calibrate(duration_sec: float = 2.0) -> float:
        """Measure ambient noise and suggest an energy_threshold.

        Records for `duration_sec` seconds (you should speak for the
        second half), then returns a threshold ~3x the noise floor.
        """
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
