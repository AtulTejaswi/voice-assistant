"""
Rule-based command interpreter.

Maps transcribed speech to structured actions.
Designed to be extended by adding new (pattern, handler) pairs.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class Command:
    action: str
    target: str = ""
    text: str = ""
    params: dict = field(default_factory=dict)
    raw_text: str = ""


HandlerFn = Callable[[Command], str]


class CommandInterpreter:
    def __init__(self):
        self._handlers: List[tuple[re.Pattern, str, HandlerFn]] = []

    def register(self, pattern: str, action: str, handler: HandlerFn):
        self._handlers.append((re.compile(pattern, re.IGNORECASE), action, handler))

    def interpret(self, text: str) -> Optional[tuple[Command, HandlerFn]]:
        for pattern, action, handler in self._handlers:
            m = pattern.search(text)
            if m:
                cmd = Command(action=action, raw_text=text, params=m.groupdict())
                if "target" in m.groupdict():
                    cmd.target = m.group("target") or ""
                if "text" in m.groupdict():
                    cmd.text = m.group("text") or ""
                if "level" in m.groupdict():
                    cmd.params["level"] = m.group("level") or ""
                return cmd, handler
        return None

    # ------------------------------------------------------------------
    # Built-in command definitions
    # ------------------------------------------------------------------

    def load_defaults(self):
        self.register(r"(?:open|launch|start)\s+(?P<target>.+)", "open_app", self._handle_open_app)
        self.register(r"type\s+(?P<text>.+)", "type_text", self._handle_type_text)
        self.register(r"press\s+(?P<target>enter|tab|escape|space|backspace|delete|up|down|left|right|home|end|page_up|page_down)", "press_key", self._handle_press_key)
        self.register(r"(?:create|make|new)\s+file\s+(?:called\s+|named\s+)?(?P<target>.+)", "create_file", self._handle_create_file)
        self.register(r"(?:open|show)\s+file\s+(?P<target>.+)", "open_file", self._handle_open_file)
        self.register(r"search\s+(?:for\s+)?(?P<text>.+)", "search_web", self._handle_search)
        self.register(r"(?:go\s+to|open|visit)\s+(?P<target>https?://\S+|[\w.-]+\.[a-z]{2,}\S*)", "open_url", self._handle_open_url)
        self.register(r"(?:play|pause|toggle)\s+(?:media|music|playback)", "media_play_pause", self._handle_media)
        self.register(r"next\s+(?:track|song|media)", "media_next", self._handle_media_next)
        self.register(r"previous\s+(?:track|song|media)", "media_previous", self._handle_media_prev)
        self.register(r"volume\s+(?P<level>up|down|max|mute|unmute|\d+)", "volume", self._handle_volume)
        self.register(r"(?:run|execute)\s+script\s+(?P<target>.+)", "run_script", self._handle_run_script)
        self.register(r"(?:what\s+)?time\s+(?:is\s+)?(?:it\s+)?(?:now\s+)?", "tell_time", self._handle_tell_time)
        self.register(r"(?:what\s+)?date\s+(?:is\s+)?(?:it\s+)?(?:today\s+)?", "tell_date", self._handle_tell_date)
        self.register(r"(?:lock|secure)\s+(?:my\s+)?(?:pc|computer|workstation)", "lock_pc", self._handle_lock_pc)
        self.register(r"(?:take\s+)?screenshot", "screenshot", self._handle_screenshot)

    # ------------------------------------------------------------------
    # Handlers — each returns a feedback string
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_open_app(cmd: Command) -> str:
        return cmd  # pass through to executor

    @staticmethod
    def _handle_type_text(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_press_key(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_create_file(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_open_file(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_search(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_open_url(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_media(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_media_next(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_media_prev(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_volume(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_run_script(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_tell_time(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_tell_date(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_lock_pc(cmd: Command) -> str:
        return cmd

    @staticmethod
    def _handle_screenshot(cmd: Command) -> str:
        return cmd
