# JARVIS — Local AI Voice Assistant

A privacy-first, LLM-powered voice assistant for Windows. Listens for "Computer" or `Ctrl+Space`, reasons with **llama3.2:3b** via Ollama, remembers facts about you, perceives your screen, and executes actions — fully offline, zero cloud APIs.

```
Wake word / hotkey → VAD recording → STT → credential guard → LLM + tools + memory → TTS feedback
```

## Features

- **LLM-powered reasoning** — replaces hard-coded regex with Ollama (llama3.2:3b). Understands conversational intent, not just exact phrases.
- **11 tools** — web search (DuckDuckGo), weather, system info (CPU/RAM/disk/battery), Python execution, directory listing, open URLs, type text, press keys, and more.
- **Three-tier memory** — short-term (20-turn rolling history), semantic (ChromaDB vector store), episodic (SQLite action log). Remembers facts about you across sessions.
- **VAD-based recording** — records until you stop speaking (energy threshold + silence timeout), no fixed clip length.
- **Credential guard** — standalone security layer blocks passwords, API keys, tokens, OTPs. 22 security tests must pass.
- **JARVIS personality** — warm, dry wit, adaptive tone. Calls you by name. British-coded courtesy.
- **Screen awareness** — captures active window title for context.
- **100% local** — Whisper STT, Ollama LLM, pyttsx3 TTS all run on your machine. Nothing leaves your computer.

## Quick Start

```powershell
# 1. Install Python 3.12+ from https://www.python.org/downloads/

# 2. Run the setup script
cd voice-assistant
.\setup.ps1

# 3. Launch
python -m src.main
```

First launch will download Whisper models (~150MB). Say **"Computer"** or press **Ctrl+Space** then speak naturally:

| Say | What happens |
|---|---|
| "open Chrome" | Launches Chrome |
| "type hello world" | Types into the active window |
| "search for Python tutorials" | Web search via DuckDuckGo |
| "what's the weather in London" | Fetches live weather |
| "how's my system doing" | Reports CPU, RAM, disk, battery |
| "run a Python script to calculate pi" | Executes code in sandbox |
| "lock my computer" | Locks the workstation |
| "remind me to check email in 10 minutes" | Sets an episodic reminder |

## Requirements

- **Python 3.12+**
- **Ollama** with `llama3.2:3b` model (`ollama pull llama3.2:3b`)
- **Windows** (for pyautogui, keyboard, active window APIs)
- ~2.5GB RAM idle, ~4GB during speech processing

## Project Structure

```
voice-assistant/
├── src/
│   ├── main.py                   # Pipeline orchestrator
│   ├── llm_core.py               # Ollama LLM client with tool-calling
│   ├── command_interpreter.py     # Thin wrapper around LLMCore
│   ├── action_executor.py         # 11 tool schemas + skill registration
│   ├── memory_manager.py          # Short-term, semantic (ChromaDB), episodic (SQLite)
│   ├── perception_engine.py       # VAD recording, screen capture, window detection
│   ├── stt_engine.py              # Speech-to-text (faster-whisper)
│   ├── tts_engine.py              # Text-to-speech (pyttsx3, async queue)
│   ├── wake_word.py               # Energy-VAD + Whisper wake word + hotkey
│   ├── personality.py             # JARVIS character, tone adaptation
│   ├── skills.py                  # Web search, weather, system info, Python exec
│   ├── hud.py                     # Semi-transparent status overlay (tkinter)
│   ├── config_manager.py          # Config validation and typed access
│   └── credential_guard.py        # Security filter — 22 test cases
├── tests/
│   └── test_credential_guard.py   # 22 security tests (MUST pass)
├── config/
│   └── assistant_config.json
├── setup.ps1
└── .gitignore
```

## Configuration

Edit `config/assistant_config.json`:

```json
{
  "llm": { "model": "llama3.2:3b", "base_url": "http://localhost:11434" },
  "stt": { "model_size": "base" },
  "wake_word": { "keyword": "computer", "energy_threshold": 0.02, "hotkey": "ctrl+space" },
  "tts": { "rate": 175, "volume": 0.9 },
  "hud": { "enabled": false },
  "safe_mode": false
}
```

- `hud.enabled`: semi-transparent overlay showing status/transcript/response
- `safe_mode`: blocks delete/remove/format/script commands
- `wake_word.keyword`: change to "jarvis" or anything you prefer
- `stt.model_size`: "tiny", "base", "small", "medium", "large-v3"

## Security

The credential guard is a hard security boundary: **no credential material ever reaches the LLM or executor**. It pattern-matches for passwords, API keys (OpenAI `sk-*`, GitHub `ghp_*`, AWS keys), JWTs, and OTPs before any command is dispatched. All 22 guard tests must pass.

```powershell
python -m pytest tests/ -v
```

## Tests

```powershell
python -m pytest tests/test_credential_guard.py -v
```

## Environment Variables (Optional)

| Variable | Purpose |
|---|---|
| `WEATHER_API_KEY` | API key for weather skill (free tier) |
| `PATH` | Must include Python and Ollama |

## Extending

Add new skills in `src/skills.py` and register them in `action_executor.py` via `register_skill_tool()`. Each tool needs a name, description, and parameter schema — the LLM handles the rest.
