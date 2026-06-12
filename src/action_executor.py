"""
Action executor — performs commands on the Windows desktop.

Uses subprocess for app launching, pyautogui for keystrokes/mouse,
pywinauto for UI automation, and os for file operations.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import pyautogui


class ActionExecutor:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    # ------------------------------------------------------------------
    # App launching
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------

    def type_text(self, text: str) -> str:
        pyautogui.typewrite(text, interval=0.02)
        return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"

    def press_key(self, key: str) -> str:
        pyautogui.press(key.lower())
        return f"Pressed {key}"

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Web / search
    # ------------------------------------------------------------------

    def search_web(self, query: str) -> str:
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        os.startfile(url)
        return f"Searched for {query}"

    def open_url(self, url: str) -> str:
        if not url.startswith("http"):
            url = "https://" + url
        os.startfile(url)
        return f"Opened {url}"

    # ------------------------------------------------------------------
    # Media keys
    # ------------------------------------------------------------------

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
            pyautogui.press("volumeup")
            pyautogui.press("volumeup")
            pyautogui.press("volumeup")
        elif level == "down":
            pyautogui.press("volumedown")
            pyautogui.press("volumedown")
            pyautogui.press("volumedown")
        elif level == "mute":
            pyautogui.press("volumemute")
        elif level == "unmute":
            pyautogui.press("volumemute")
        elif level == "max":
            for _ in range(10):
                pyautogui.press("volumeup")
        else:
            try:
                val = int(level)
                val = max(0, min(100, val))
                for _ in range(val // 10):
                    pyautogui.press("volumeup")
            except ValueError:
                pass
        return f"Volume {level}"

    # ------------------------------------------------------------------
    # Script execution
    # ------------------------------------------------------------------

    def run_script(self, name: str) -> str:
        path = Path(name)
        if not path.is_absolute():
            path = Path.cwd() / name
        if path.exists():
            subprocess.Popen(["python", str(path)], shell=True)
            return f"Running {path}"
        return f"Script not found: {path}"

    # ------------------------------------------------------------------
    # System info
    # ------------------------------------------------------------------

    def tell_time(self) -> str:
        return datetime.now().strftime("It is %I:%M %p")

    def tell_date(self) -> str:
        return datetime.now().strftime("Today is %A, %B %d, %Y")

    def lock_pc(self) -> str:
        subprocess.run("rundll32.exe user32.dll,LockWorkStation")
        return "Locking your PC"

    def screenshot(self) -> str:
        path = Path.home() / "Pictures" / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        pyautogui.screenshot(str(path))
        return f"Screenshot saved to {path}"
