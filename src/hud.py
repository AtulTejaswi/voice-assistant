"""
HUD overlay — semi-transparent status window.

Shows listening status, current transcript, assistant response.
Togglable via config (hud.enabled).
"""

import threading
import tkinter as tk
from typing import Optional


class HUD:
    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._root: Optional[tk.Tk] = None
        self._status_var: Optional[tk.StringVar] = None
        self._transcript_var: Optional[tk.StringVar] = None
        self._response_var: Optional[tk.StringVar] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not self._enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._root = tk.Tk()
        self._root.title("JARVIS")
        self._root.attributes("-topmost", True)
        self._root.attributes("-alpha", 0.85)
        self._root.overrideredirect(True)
        self._root.configure(bg="#1a1a2e")

        # Position: bottom-right
        ws = self._root.winfo_screenwidth()
        hs = self._root.winfo_screenheight()
        w, h = 380, 180
        self._root.geometry(f"{w}x{h}+{ws - w - 20}+{hs - h - 60}")

        self._status_var = tk.StringVar(value="● Standby")
        self._transcript_var = tk.StringVar(value="")
        self._response_var = tk.StringVar(value="")

        font_style = ("Segoe UI", 10)
        tk.Label(self._root, textvariable=self._status_var, fg="#00d4aa",
                 bg="#1a1a2e", font=("Segoe UI", 11, "bold"), anchor="w").pack(
                 fill="x", padx=12, pady=(10, 2))

        tk.Label(self._root, textvariable=self._transcript_var, fg="#e0e0e0",
                 bg="#1a1a2e", font=font_style, anchor="w", wraplength=360,
                 justify="left").pack(fill="x", padx=12, pady=2)

        tk.Label(self._root, textvariable=self._response_var, fg="#88ccff",
                 bg="#1a1a2e", font=font_style, anchor="w", wraplength=360,
                 justify="left").pack(fill="x", padx=12, pady=2)

        self._root.mainloop()

    def set_status(self, status: str):
        if not self._enabled or not self._status_var:
            return
        self._status_var.set(f"● {status}")

    def set_transcript(self, text: str):
        if not self._enabled or not self._transcript_var:
            return
        self._transcript_var.set(f"You: {text[:80]}")

    def set_response(self, text: str):
        if not self._enabled or not self._response_var:
            return
        self._response_var.set(text[:120])

    def stop(self):
        if self._root:
            self._root.quit()
