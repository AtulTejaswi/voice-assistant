"""
Skill modules for JARVIS.
Each skill is a class with a `register(executor)` method that adds tools.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import psutil


def register_skills(executor):
    """Register all skill tools with the executor."""
    executor.register_skill_tool(
        "web_search",
        "Search the web for current information using DuckDuckGo",
        {"query": {"type": "string", "description": "Search query"}},
        required=["query"],
        handler=_web_search,
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


def _web_search(query: str) -> str:
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
