"""
JARVIS — main entry point.

Pipeline: wake/hotkey → VAD recording → STT → guard → LLM reason (with memory) → TTS feedback
"""

import time

from src.credential_guard import CredentialGuard
from src.command_interpreter import CommandInterpreter
from src.action_executor import ActionExecutor
from src.llm_core import LLMCore
from src.memory_manager import MemoryManager
from src.perception_engine import PerceptionEngine
from src.stt_engine import STTEngine
from src.tts_engine import TTSEngine
from src.wake_word import ActivationEngine


class VoiceAssistant:
    def __init__(self):
        self.memory = MemoryManager()
        self.guard = CredentialGuard()
        self.executor = ActionExecutor()
        self.llm = LLMCore(model="llama3.2:3b", memory=self.memory)
        self.interpreter = CommandInterpreter(self.llm, self.executor)
        self.stt = STTEngine(model_size="base", device="auto")
        self.tts = TTSEngine()
        self.perception = PerceptionEngine()
        self.activation = ActivationEngine(wake_word="computer", hotkey="ctrl+space")

        self.activation.on_activate(self._on_activated)
        self.activation.on_deactivate(self._on_deactivated)

    def run(self):
        # Greet with memory
        name = self.llm._user_name or "there"
        self.tts.speak(f"JARVIS ready, {name}")
        print(f"[JARVIS] Ready. Say 'Computer' or press Ctrl+Space.")
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

    def _on_activated(self):
        print("[JARVIS] Listening...")
        self.tts.speak("Listening")

    def _on_deactivated(self):
        print("[JARVIS] Stopped listening")

    def _listen_and_process(self):
        # VAD-based recording (not fixed 5s)
        result = self.perception.record_until_silence()
        if result is None:
            self.activation._deactivate()
            return

        transcript = self.stt.transcribe(result.audio, sample_rate=result.sample_rate)
        if not transcript:
            self.activation._deactivate()
            return

        print(f"[You] {transcript}")

        # Guard
        guard_result = self.guard.inspect(transcript)
        if not guard_result.safe:
            print(f"[Guard] BLOCKED: {guard_result.reason}")
            self.tts.speak("I cannot handle credentials. Please enter them manually.")
            self.activation._deactivate()
            return

        # Screen context
        screen = self.perception.capture_screen(save=True)
        window = self.perception.active_window_title()
        if window:
            print(f"[Context] Active window: {window}")

        # LLM reasoning
        success, response = self.interpreter.interpret(transcript)
        if not success:
            self.tts.speak("I had trouble processing that.")
            self.activation._deactivate()
            return

        print(f"[JARVIS] {response}")
        self.tts.speak(response)
        self.activation._deactivate()


def main():
    assistant = VoiceAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.shutdown()


if __name__ == "__main__":
    main()
