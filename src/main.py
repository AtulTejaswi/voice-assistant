"""
Voice-Controlled Automation Assistant — main entry point.

Pipeline: wake/hotkey → audio capture → STT → guard → interpret → execute → feedback
"""

import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from src.credential_guard import CredentialGuard
from src.command_interpreter import CommandInterpreter
from src.action_executor import ActionExecutor
from src.stt_engine import STTEngine
from src.tts_engine import TTSEngine
from src.wake_word import ActivationEngine


class VoiceAssistant:
    def __init__(self):
        self.guard = CredentialGuard()
        self.interpreter = CommandInterpreter()
        self.executor = ActionExecutor()
        self.stt = STTEngine(model_size="base", device="auto")
        self.tts = TTSEngine()
        self.activation = ActivationEngine(wake_word="computer", hotkey="ctrl+space")

        self.interpreter.load_defaults()

        # Wire up activation callbacks
        self.activation.on_activate(self._on_activated)
        self.activation.on_deactivate(self._on_deactivated)

        self._sample_rate = 16000
        self._duration = 5  # seconds per recording chunk

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):
        self.tts.speak("Assistant ready. Press Ctrl+Win+Space or say Computer.")
        print("[Assistant] Ready. Press Ctrl+Win+Space or say 'Computer' to activate.")
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
        print("[Assistant] Shut down.")

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _on_activated(self):
        print("[Assistant] Listening... (speak your command)")
        self.tts.speak("Listening")

    def _on_deactivated(self):
        print("[Assistant] Stopped listening")

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

        # Guard
        guard_result = self.guard.inspect(transcript)
        if not guard_result.safe:
            print(f"[Guard] BLOCKED: {guard_result.reason}")
            self.tts.speak("I cannot handle that. Please enter any credentials manually.")
            self.activation._deactivate()
            return

        # Interpret
        result = self.interpreter.interpret(transcript)
        if result is None:
            print(f"[Assistant] Command not recognized: {transcript}")
            self.tts.speak("Sorry, I did not understand that command")
            self.activation._deactivate()
            return

        cmd, handler = result

        # Execute
        feedback = handler(cmd)
        if isinstance(feedback, str):
            print(f"[Assistant] {feedback}")
            self.tts.speak(feedback)
        else:
            # handler returned the Command — executor handles it
            feedback = self._execute(cmd)
            print(f"[Assistant] {feedback}")
            self.tts.speak(feedback)

        self.activation._deactivate()

    def _execute(self, cmd) -> str:
        dispatch = {
            "open_app": self.executor.open_app,
            "type_text": self.executor.type_text,
            "press_key": self.executor.press_key,
            "create_file": self.executor.create_file,
            "open_file": self.executor.open_file,
            "search_web": self.executor.search_web,
            "open_url": self.executor.open_url,
            "media_play_pause": lambda _: self.executor.media_play_pause(),
            "media_next": lambda _: self.executor.media_next(),
            "media_previous": lambda _: self.executor.media_previous(),
            "volume": self.executor.volume,
            "run_script": self.executor.run_script,
            "tell_time": lambda _: self.executor.tell_time(),
            "tell_date": lambda _: self.executor.tell_date(),
            "lock_pc": lambda _: self.executor.lock_pc(),
            "screenshot": lambda _: self.executor.screenshot(),
        }
        handler = dispatch.get(cmd.action)
        if handler is None:
            return f"Unknown action: {cmd.action}"
        arg = cmd.target or cmd.text or cmd.params.get("level", "")
        return handler(arg) if arg else handler(None)

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
