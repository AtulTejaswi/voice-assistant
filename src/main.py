"""
Voice-Controlled AI Assistant — main entry point.

Pipeline: wake/hotkey → audio capture → STT → guard → LLM reason → execute → TTS feedback
"""

import time

import numpy as np
import sounddevice as sd

from src.credential_guard import CredentialGuard
from src.command_interpreter import CommandInterpreter
from src.action_executor import ActionExecutor
from src.llm_core import LLMCore
from src.stt_engine import STTEngine
from src.tts_engine import TTSEngine
from src.wake_word import ActivationEngine


class VoiceAssistant:
    def __init__(self):
        self.guard = CredentialGuard()
        self.executor = ActionExecutor()
        self.llm = LLMCore(model="llama3.2:3b")
        self.interpreter = CommandInterpreter(self.llm, self.executor)
        self.stt = STTEngine(model_size="base", device="auto")
        self.tts = TTSEngine()
        self.activation = ActivationEngine(wake_word="computer", hotkey="ctrl+space")

        self.activation.on_activate(self._on_activated)
        self.activation.on_deactivate(self._on_deactivated)

        self._sample_rate = 16000
        self._duration = 5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):
        self.tts.speak("Assistant ready")
        print("[JARVIS] Ready. Say 'Computer' or press Ctrl+Space.")
        self.activation.start()
        try:
            while True:
                if self.activation.is_listening:
                    self._listen_and_process()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        self.activation.stop()
        self.tts.speak("Shutting down")
        print("[JARVIS] Shut down.")

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _on_activated(self):
        print("[JARVIS] Listening...")
        self.tts.speak("Listening")

    def _on_deactivated(self):
        print("[JARVIS] Stopped listening")

    def _listen_and_process(self):
        audio = self._record_audio()
        if audio is None or len(audio) == 0:
            self.activation._deactivate()
            return

        transcript = self.stt.transcribe(audio, sample_rate=self._sample_rate)
        if not transcript:
            self.activation._deactivate()
            return

        print(f"[You] {transcript}")

        # Guard — blocks credentials before LLM sees them
        guard_result = self.guard.inspect(transcript)
        if not guard_result.safe:
            print(f"[Guard] BLOCKED: {guard_result.reason}")
            self.tts.speak("I cannot handle credentials. Please enter them manually.")
            self.activation._deactivate()
            return

        # LLM reasoning — interprets intent and executes tools
        success, response = self.interpreter.interpret(transcript)
        if not success:
            self.tts.speak("I had trouble processing that.")
            self.activation._deactivate()
            return

        print(f"[JARVIS] {response}")
        self.tts.speak(response)
        self.activation._deactivate()

    def _record_audio(self) -> np.ndarray:
        try:
            recording = sd.rec(
                int(self._duration * self._sample_rate),
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            return recording.flatten()
        except Exception as e:
            print(f"[Audio] Error: {e}")
            return None


def main():
    assistant = VoiceAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.shutdown()


if __name__ == "__main__":
    main()
