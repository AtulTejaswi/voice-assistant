"""
Text-to-speech feedback engine using pyttsx3 (local).

Speech is queued and processed sequentially on a single background thread
so speak() is non-blocking and safe to call concurrently.
"""

import pyttsx3
import queue
import threading
import time


class TTSEngine:
    def __init__(self):
        self._rate = 175
        self._volume = 0.9
        self._engine = None
        self._queue: queue.Queue[str] = queue.Queue()
        self._running = True
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        # Lazy init engine in background
        threading.Thread(target=self._lazy_init, daemon=True).start()

    def _lazy_init(self):
        try:
            eng = pyttsx3.init()
            eng.setProperty("rate", self._rate)
            eng.setProperty("volume", self._volume)
            self._engine = eng
        except Exception as e:
            print(f"[TTS] Init failed: {e}")

    def _run(self):
        while self._running:
            try:
                text = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if self._engine:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as e:
                    print(f"[TTS] Speak error: {e}")

    def speak(self, text: str):
        if self._running:
            self._queue.put(text)

    def wait_until_done(self, timeout: float = 5.0):
        """Block until queue is empty (useful before shutdown)."""
        deadline = time.time() + timeout
        while time.time() < deadline and not self._queue.empty():
            time.sleep(0.05)

    def set_rate(self, rate: int):
        self._rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        if self._engine:
            self._engine.setProperty("volume", self._volume)

    def stop(self):
        self._running = False
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
