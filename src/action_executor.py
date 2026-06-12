"""
Action executor — performs commands on the Windows desktop.

Each method has a corresponding JSON tool schema for LLM tool-calling.
"""

import os
import subprocess
import urllib.parse
from datetime import datetime
from pathlib import Path

import pyautogui


class ActionExecutor:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    APP_ALIASES = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "edge": "msedge",
        "microsoft edge": "msedge",
        "firefox": "firefox",
        "notepad": "notepad",
        "vs code": "code",
        "visual studio code": "code",
        "terminal": "cmd",
        "command prompt": "cmd",
        "powershell": "powershell",
        "explorer": "explorer",
        "file explorer": "explorer",
        "calculator": "calc",
        "spotify": "spotify",
        "settings": "ms-settings:",
    }

    # ------------------------------------------------------------------
    # Tool schema definitions
    # ------------------------------------------------------------------

    @staticmethod
    def tool_schemas() -> dict:
        return {
            "launch_app": {
                "name": "launch_app",
                "description": "Launch an application by name (chrome, notepad, vs code, explorer, calculator, spotify, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Application name"},
                    },
                    "required": ["name"],
                },
            },
            "type_keys": {
                "name": "type_keys",
                "description": "Type text or press a key (enter, tab, escape, space, backspace, delete, arrow keys) into the active window",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["type", "press"], "description": "'type' for text, 'press' for a single key"},
                        "value": {"type": "string", "description": "Text to type or key name to press"},
                    },
                    "required": ["action", "value"],
                },
            },
            "file_ops": {
                "name": "file_ops",
                "description": "Create or open a file on the desktop",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["create", "open"], "description": "create a new file or open an existing one"},
                        "filename": {"type": "string", "description": "Filename (e.g., notes.txt)"},
                    },
                    "required": ["operation", "filename"],
                },
            },
            "web_search": {
                "name": "web_search",
                "description": "Search the web using Google or open a specific URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["search", "open_url"], "description": "'search' for Google search, 'open_url' to visit a website"},
                        "value": {"type": "string", "description": "Search query or URL"},
                    },
                    "required": ["action", "value"],
                },
            },
            "media_control": {
                "name": "media_control",
                "description": "Control media playback and volume: play/pause, next, previous, volume up/down/mute/max",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "enum": ["play_pause", "next", "previous", "volume_up", "volume_down", "volume_mute", "volume_max"],
                            "description": "Media command to execute",
                        }
                    },
                    "required": ["command"],
                },
            },
            "system_action": {
                "name": "system_action",
                "description": "Perform system actions: tell the current time, tell today's date, lock the PC, or take a screenshot",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["time", "date", "lock", "screenshot"],
                            "description": "System action to perform",
                        }
                    },
                    "required": ["action"],
                },
            },
            "run_script": {
                "name": "run_script",
                "description": "Execute a Python script file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Script filename or path"},
                    },
                    "required": ["name"],
                },
            },
        }

    def get_handlers(self) -> dict:
        return {
            "launch_app": self.open_app,
            "type_keys": self.type_keys,
            "file_ops": self.file_ops,
            "web_search": self.web_search,
            "media_control": self.media_control,
            "system_action": self.system_action,
            "run_script": self.run_script,
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Consolidated handlers (used by LLM tools)
    # ------------------------------------------------------------------

    def type_keys(self, action: str, value: str) -> str:
        if action == "type":
            return self.type_text(value)
        elif action == "press":
            return self.press_key(value)
        return f"Unknown type_keys action: {action}"

    def file_ops(self, operation: str, filename: str) -> str:
        if operation == "create":
            return self.create_file(filename)
        elif operation == "open":
            return self.open_file(filename)
        return f"Unknown file operation: {operation}"

    def web_search(self, action: str, value: str) -> str:
        if action == "search":
            return self.search_web(value)
        elif action == "open_url":
            return self.open_url(value)
        return f"Unknown web action: {action}"

    def media_control(self, command: str) -> str:
        mapping = {
            "play_pause": self.media_play_pause,
            "next": self.media_next,
            "previous": self.media_previous,
            "volume_up": lambda: self.volume("up"),
            "volume_down": lambda: self.volume("down"),
            "volume_mute": lambda: self.volume("mute"),
            "volume_max": lambda: self.volume("max"),
        }
        handler = mapping.get(command)
        if handler:
            return handler()
        return f"Unknown media command: {command}"

    def system_action(self, action: str) -> str:
        mapping = {
            "time": self.tell_time,
            "date": self.tell_date,
            "lock": self.lock_pc,
            "screenshot": self.screenshot,
        }
        handler = mapping.get(action)
        if handler:
            return handler()
        return f"Unknown system action: {action}"

    def open_app(self, name: str) -> str:
        name = name.strip().lower()
        app = self.APP_ALIASES.get(name, name)
        try:
            if app.startswith("ms-"):
                os.startfile(app)
            else:
                subprocess.Popen(app, shell=True)
            return f"Opened {name}"
        except Exception as e:
            return f"Failed to open {name}: {e}"

    def type_text(self, text: str) -> str:
        pyautogui.typewrite(text, interval=0.02)
        preview = text[:50]
        return f"Typed: {preview}{'...' if len(text) > 50 else ''}"

    def press_key(self, key: str) -> str:
        pyautogui.press(key.lower())
        return f"Pressed {key}"

    def create_file(self, name: str) -> str:
        path = Path.home() / "Desktop" / name
        path.touch()
        return f"Created file {path}"

    def open_file(self, name: str) -> str:
        path = Path(name)
        if not path.is_absolute():
            path = Path.home() / "Desktop" / name
        if path.exists():
            os.startfile(path)
            return f"Opened file {path}"
        return f"File not found: {path}"

    def search_web(self, query: str) -> str:
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        os.startfile(url)
        return f"Searched for {query}"

    def open_url(self, url: str) -> str:
        if not url.startswith("http"):
            url = "https://" + url
        os.startfile(url)
        return f"Opened {url}"

    def media_play_pause(self) -> str:
        pyautogui.press("playpause")
        return "Toggled play/pause"

    def media_next(self) -> str:
        pyautogui.press("nexttrack")
        return "Next track"

    def media_previous(self) -> str:
        pyautogui.press("prevtrack")
        return "Previous track"

    def volume(self, level: str) -> str:
        level = level.lower()
        if level == "up":
            for _ in range(3):
                pyautogui.press("volumeup")
        elif level == "down":
            for _ in range(3):
                pyautogui.press("volumedown")
        elif level in ("mute", "unmute"):
            pyautogui.press("volumemute")
        elif level == "max":
            for _ in range(10):
                pyautogui.press("volumeup")
        else:
            try:
                val = max(0, min(100, int(level)))
                for _ in range(val // 10):
                    pyautogui.press("volumeup")
            except ValueError:
                pass
        return f"Volume {level}"

    def run_script(self, name: str) -> str:
        path = Path(name)
        if not path.is_absolute():
            path = Path.cwd() / name
        if path.exists():
            subprocess.Popen(["python", str(path)], shell=True)
            return f"Running {path}"
        return f"Script not found: {path}"

    def tell_time(self) -> str:
        return datetime.now().strftime("It is %I:%M %p")

    def tell_date(self) -> str:
        return datetime.now().strftime("Today is %A, %B %d, %Y")

    def lock_pc(self) -> str:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True, capture_output=True)
        return "Locking your PC"

    def screenshot(self) -> str:
        path = Path.home() / "Pictures" / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        pyautogui.screenshot(str(path))
        return f"Screenshot saved to {path.name}"
