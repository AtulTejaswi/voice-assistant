"""
Skill modules for JARVIS.
Each skill is a class with a `register(executor)` method that adds tools.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import psutil

# Module-level TTS reference for timed reminders
tts_ref = None


def register_skills(executor, tts=None):
    """Register all skill tools with the executor."""
    global tts_ref
    tts_ref = tts

    executor.register_skill_tool(
        "ddg_search",
        "Search the web using DuckDuckGo for current information",
        {"query": {"type": "string", "description": "Search query"}},
        required=["query"],
        handler=_ddg_search,
    )
    executor.register_skill_tool(
        "get_weather",
        "Get current weather for a city using web search",
        {"city": {"type": "string", "description": "City name"}},
        required=["city"],
        handler=_get_weather,
    )
    executor.register_skill_tool(
        "system_info",
        "Get detailed system status: CPU, memory, disk usage, battery",
        {"info_type": {"type": "string", "enum": ["cpu", "memory", "disk", "battery", "all"], "description": "What system info to retrieve"}},
        required=["info_type"],
        handler=_system_info,
    )
    executor.register_skill_tool(
        "run_python_code",
        "Execute a short Python snippet and return the result",
        {"code": {"type": "string", "description": "Python code to execute"}},
        required=["code"],
        handler=_run_python_code,
    )
    executor.register_skill_tool(
        "list_directory",
        "List files in a directory",
        {"path": {"type": "string", "description": "Directory path (defaults to current)"}},
        handler=_list_directory,
    )
    executor.register_skill_tool(
        "calibrate_microphone",
        "Calibrate the microphone sensitivity. Records for 2 seconds while you speak, then adjusts the energy threshold.",
        {},
        handler=_calibrate_microphone,
    )
    executor.register_skill_tool(
        "set_reminder",
        "Set a spoken reminder after N minutes. JARVIS will say it aloud.",
        {
            "task": {"type": "string", "description": "What to remind the user about"},
            "minutes": {"type": "number", "description": "How many minutes from now"}
        },
        required=["task", "minutes"],
        handler=lambda task, minutes: _set_reminder(task, minutes, tts_ref),
    )
    executor.register_skill_tool(
        "clipboard_read",
        "Read the current text from the clipboard so JARVIS can act on it",
        {},
        handler=_clipboard_read,
    )
    executor.register_skill_tool(
        "clipboard_write",
        "Copy text to the clipboard",
        {"text": {"type": "string", "description": "Text to copy"}},
        required=["text"],
        handler=_clipboard_write,
    )
    executor.register_skill_tool(
        "tell_joke",
        "Tell a short witty joke in JARVIS style",
        {},
        handler=_tell_joke,
    )


def _ddg_search(query: str) -> str:
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(query, max_results=3))
        if not results:
            return f"No results for '{query}'"
        return "\n".join(f"{r['title']}: {r['href']}" for r in results)
    except Exception as e:
        return f"Search failed: {e}"


def _get_weather(city: str) -> str:
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(f"weather {city} today", max_results=1))
        if results:
            return results[0]["body"][:300]
        return f"Could not find weather for {city}"
    except Exception as e:
        return f"Weather lookup failed: {e}"


def _system_info(info_type: str) -> str:
    if info_type in ("cpu", "all"):
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_count = psutil.cpu_count()
        cpu_info = f"CPU: {cpu_percent}% used, {cpu_count} cores"
    else:
        cpu_info = ""

    if info_type in ("memory", "all"):
        mem = psutil.virtual_memory()
        mem_info = f"RAM: {mem.percent}% used ({mem.used >> 30}GB/{mem.total >> 30}GB)"
    else:
        mem_info = ""

    if info_type in ("disk", "all"):
        disk = psutil.disk_usage("/")
        disk_info = f"Disk: {disk.percent}% used ({disk.free >> 30}GB free)"
    else:
        disk_info = ""

    if info_type in ("battery", "all"):
        try:
            batt = psutil.sensors_battery()
            if batt:
                batt_info = f"Battery: {batt.percent}% {'plugged in' if batt.power_plugged else 'on battery'}"
            else:
                batt_info = "Battery: not detected"
        except Exception:
            batt_info = "Battery: unavailable"
    else:
        batt_info = ""

    return "\n".join(filter(None, [cpu_info, mem_info, disk_info, batt_info]))


def _run_python_code(code: str) -> str:
    try:
        safe_globals = {"__builtins__": __builtins__}
        local_vars = {}
        exec(code, safe_globals, local_vars)
        output = str(local_vars.get("result", local_vars.get("_", "")))
        return output or "Code executed successfully (no explicit result)"
    except Exception as e:
        return f"Error: {e}"


def _calibrate_microphone() -> str:
    """Record 2s of audio, measure speech level, return suggested threshold."""
    try:
        from src.mic_utils import find_best_device, resample_to_16k, convert_to_float
        import sounddevice as sd
        import numpy as np
        mic = find_best_device()
        sr = mic["samplerate"]
        dtype = mic["dtype"]
        device = mic["index"]
        print(f"[Calibrate] Speak now for 2 seconds (device [{device}] @ {sr}Hz)...")
        rec = sd.rec(int(2 * sr), samplerate=sr, channels=1, dtype=dtype, device=device)
        sd.wait()
        data = convert_to_float(rec.flatten(), dtype)
        if sr != 16000:
            data = resample_to_16k(data, sr)
        levels = [np.sqrt(np.mean(data[i:i+1600] ** 2)) for i in range(0, len(data), 1600)]
        quiet = sorted(levels)[:len(levels)//3]
        noise_floor = float(np.mean(quiet)) if quiet else 0.001
        suggested = max(noise_floor * 3, 0.002)
        peak = float(np.max(np.abs(data)))
        return (
            f"Calibration complete.\n"
            f"  Noise floor: {noise_floor:.5f}\n"
            f"  Peak level: {peak:.5f}\n"
            f"  Suggested energy_threshold: {suggested:.5f}\n\n"
            f"Update config/assistant_config.json:\n"
            f'  "energy_threshold": {suggested:.5f}'
        )
    except Exception as e:
        return f"Calibration failed: {e}"


def _list_directory(path: str = ".") -> str:
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Directory not found: {path}"
        entries = []
        for item in p.iterdir():
            suffix = "/" if item.is_dir() else ""
            entries.append(f"{item.name}{suffix}")
        return "\n".join(entries[:30]) + (f"\n... and {len(entries) - 30} more" if len(entries) > 30 else "")
    except Exception as e:
        return f"Error listing directory: {e}"


def _set_reminder(task: str, minutes: float, tts) -> str:
    import threading
    def _fire():
        if tts:
            tts.speak(f"Reminder, sir: {task}")
    t = threading.Timer(minutes * 60, _fire)
    t.daemon = True
    t.start()
    return f"Reminder set for {minutes} minutes from now."


def _clipboard_read() -> str:
    try:
        import pyperclip
        text = pyperclip.paste()
        return text[:500] if text else "Clipboard is empty."
    except Exception as e:
        return f"Could not read clipboard: {e}"


def _clipboard_write(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        return "Copied to clipboard."
    except Exception as e:
        return f"Could not write to clipboard: {e}"


def _tell_joke() -> str:
    try:
        import requests
        payload = {
            "model": "llama3.2:3b",
            "messages": [
                {"role": "system", "content": "You are JARVIS. Tell one very short, dry, witty joke. One sentence only. No setup/punchline labels."},
                {"role": "user", "content": "Tell me a joke."}
            ],
            "stream": False
        }
        r = requests.post("http://localhost:11434/v1/chat/completions", json=payload, timeout=15)
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "My humor circuits appear to be offline, sir."
