"""
JARVIS — main entry point.

Pipeline: wake/hotkey → VAD recording → STT → guard → LLM reason (with memory) → TTS feedback
"""

import subprocess
import threading
import time

import requests

from src.credential_guard import CredentialGuard
from src.command_interpreter import CommandInterpreter
from src.action_executor import ActionExecutor
from src.llm_core import LLMCore
from src.memory_manager import MemoryManager
from src.perception_engine import PerceptionEngine
from src.stt_engine import STTEngine
from src.tts_engine import TTSEngine
from src.wake_word import ActivationEngine
from src.config_manager import ConfigManager
from src.hud import HUD
from src import skills


class VoiceAssistant:
    def __init__(self):
        self._running = True
        self.config = ConfigManager()
        self.memory = MemoryManager()
        self.guard = CredentialGuard()
        self.executor = ActionExecutor()
        self.tts = TTSEngine()
        self.tts.set_rate(self.config.tts_rate)
        self.tts.set_volume(self.config.tts_volume)
        skills.register_skills(self.executor, tts=self.tts)
        self.llm = LLMCore(
            model=self.config.llm_model,
            base_url=self.config.llm_base_url,
            memory=self.memory,
        )
        self.interpreter = CommandInterpreter(self.llm, self.executor)
        self.stt = STTEngine(model_size=self.config.stt_model, device="auto")
        self.perception = PerceptionEngine(
            energy_threshold=self.config.get("wake_word.energy_threshold", 0.04),
            silence_timeout_sec=self.config.get("recording.silence_timeout_sec", 1.5),
            max_record_sec=self.config.get("recording.max_record_sec", 30.0),
        )
        self.activation = ActivationEngine(
            wake_word=self.config.wake_word,
            hotkey=self.config.hotkey,
        )
        self.activation.on_activate(self._on_activated)
        self.activation.on_deactivate(self._on_deactivated)
        self.hud = HUD(enabled=self.config.hud_enabled)

    def _check_ollama(self) -> bool:
        try:
            r = requests.get(f"{self.config.llm_base_url}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                print(f"[JARVIS] Ollama online. Models: {models}")
                model = self.config.llm_model
                if model not in models and not any(model in m for m in models):
                    print(f"[JARVIS] Model '{model}' not found. Auto-pulling...")
                    self._pull_model()
                return True
        except Exception as e:
            print(f"[JARVIS] Ollama not reachable: {e}")
            self.tts.speak("Warning: Ollama is not running. Please start Ollama and restart me.")
            return False
        return False

    def _pull_model(self):
        def _do_pull():
            self.tts.speak(f"Downloading {self.config.llm_model}. This may take a few minutes.")
            print(f"[JARVIS] Pulling {self.config.llm_model}...")
            result = subprocess.run(
                ["ollama", "pull", self.config.llm_model],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.tts.speak("Model downloaded. I am ready.")
            else:
                self.tts.speak("Model download failed. Check your internet connection.")
                print(f"[JARVIS] Pull error: {result.stderr}")

        threading.Thread(target=_do_pull, daemon=True).start()

    def _print_status(self):
        print("\n" + "=" * 50)
        print("  J.A.R.V.I.S  -  Online")
        print("=" * 50)
        print(f"  LLM model   : {self.config.llm_model}")
        print(f"  LLM backend : Ollama ({self.config.llm_base_url})")
        print(f"  STT model   : {self.config.stt_model}")
        print(f"  Wake word   : '{self.config.wake_word}'")
        print(f"  Hotkey      : {self.config.hotkey}")
        print(f"  Safe mode   : {self.config.safe_mode}")
        print("=" * 50 + "\n")

    def run(self):
        self.hud.start()
        self._check_ollama()
        self._print_status()
        name = self.llm._user_name or "sir"
        self.tts.speak(f"JARVIS ready, {name}")
        self.hud.set_status("Standby")
        print(f"[JARVIS] Ready. Say 'Computer' or press Ctrl+Space.")
        self.activation.start()
        try:
            while self._running:
                if self.activation.is_listening:
                    self._listen_and_process()
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        self._running = False
        self.activation.stop()
        self.hud.set_status("Shutting down")
        self.tts.speak("Shutting down")
        self.tts.wait_until_done(timeout=3.0)
        self.hud.stop()
        print("[JARVIS] Shut down.")

    def _on_activated(self):
        self.hud.set_status("Listening")
        print("[JARVIS] Listening...")
        self.tts.speak("Listening")

    def _on_deactivated(self):
        self.hud.set_status("Standby")
        print("[JARVIS] Stopped listening")

    def _listen_and_process(self):
        print("[JARVIS] Starting recording...")
        result = self.perception.record_until_silence()
        if result is None:
            self.activation._deactivate()
            return

        transcript = self.stt.transcribe(result.audio, sample_rate=result.sample_rate)
        if not transcript:
            self.activation._deactivate()
            return

        self.hud.set_transcript(transcript)
        print(f"[You] {transcript}")

        # Safe mode check
        if self.config.safe_mode and any(w in transcript.lower() for w in ["script", "delete", "remove", "format"]):
            self.tts.speak("Safe mode is enabled. I cannot perform that action.")
            self.activation._deactivate()
            return

        # Guard
        guard_result = self.guard.inspect(transcript)
        if not guard_result.safe:
            print(f"[Guard] BLOCKED: {guard_result.reason}")
            self.tts.speak("I cannot handle credentials. Please enter them manually.")
            self.activation._deactivate()
            return

        # Screen context
        window = self.perception.active_window_title()
        if window:
            print(f"[Context] Active window: {window}")

        # LLM reasoning
        self.hud.set_status("Thinking")
        success, response = self.interpreter.interpret(transcript)
        if not success:
            self.tts.speak("I had trouble processing that.")
            self.activation._deactivate()
            return

        self.hud.set_status("Speaking")
        self.hud.set_response(response)
        print(f"[JARVIS] {response}")
        self.tts.speak(response)

        # Multi-turn: if JARVIS asked a question, stay listening
        if response.strip().endswith("?"):
            print("[JARVIS] Staying in listen mode for follow-up...")
        else:
            self.activation._deactivate()


def main():
    assistant = VoiceAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.shutdown()


if __name__ == "__main__":
    main()
