"""
Text-to-speech feedback engine using pyttsx3 (local).
"""

import pyttsx3


class TTSEngine:
    def __init__(self):
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", 175)
        self._engine.setProperty("volume", 0.9)

    def speak(self, text: str):
        self._engine.say(text)
        self._engine.runAndWait()

    def set_rate(self, rate: int):
        self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float):
        self._engine.setProperty("volume", max(0.0, min(1.0, volume)))
