"""
Configuration manager — loads, validates, and provides typed access to config.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class ConfigError(Exception):
    pass


class ConfigManager:
    def __init__(self, path: Optional[str] = None):
        paths_to_try = [
            path,
            str(Path.cwd() / "config" / "assistant_config.json"),
            str(Path(__file__).resolve().parent.parent / "config" / "assistant_config.json"),
            str(Path.home() / ".jarvis" / "config.json"),
        ]

        self._data: dict[str, Any] = {}
        for p in paths_to_try:
            if p and Path(p).exists():
                with open(p) as f:
                    self._data = json.load(f)
                break

        if not self._data:
            raise ConfigError("No config file found")

        self.validate()

    def validate(self):
        """Validate required sections. Raises ConfigError on missing critical fields."""
        required = ["llm", "stt", "wake_word", "tts"]
        for section in required:
            if section not in self._data:
                raise ConfigError(f"Missing required config section: {section}")

        llm = self._data.get("llm", {})
        if not llm.get("model"):
            self._data["llm"]["model"] = "llama3.2:3b"
        if not llm.get("base_url"):
            self._data["llm"]["base_url"] = "http://localhost:11434"

    @property
    def llm_model(self) -> str:
        return self._data.get("llm", {}).get("model", "llama3.2:3b")

    @property
    def llm_base_url(self) -> str:
        return self._data.get("llm", {}).get("base_url", "http://localhost:11434")

    @property
    def stt_model(self) -> str:
        return self._data.get("stt", {}).get("model_size", "base")

    @property
    def wake_word(self) -> str:
        return self._data.get("wake_word", {}).get("keyword", "computer")

    @property
    def hotkey(self) -> str:
        return self._data.get("wake_word", {}).get("hotkey", "ctrl+space")

    @property
    def tts_rate(self) -> int:
        return self._data.get("tts", {}).get("rate", 175)

    @property
    def tts_volume(self) -> float:
        return self._data.get("tts", {}).get("volume", 0.9)

    @property
    def hud_enabled(self) -> bool:
        return self._data.get("hud", {}).get("enabled", False)

    @property
    def safe_mode(self) -> bool:
        """When enabled, disables file/script execution tools."""
        return self._data.get("safe_mode", False)

    @safe_mode.setter
    def safe_mode(self, value: bool):
        self._data["safe_mode"] = value

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def reload(self):
        """Re-read config from disk."""
        self.__init__()
