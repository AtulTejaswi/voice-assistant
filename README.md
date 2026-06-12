# Voice-Controlled Automation Assistant

A local, privacy-first voice assistant for Windows that listens for voice commands and performs actions on your computer — opening apps, typing text, searching the web, controlling media, managing files, and more.

```
Wake word / hotkey → STT → credential guard → intent parsing → execution → TTS feedback
```

## Features

- **100% local** — speech-to-text (Whisper), wake word detection, and TTS all run on your machine. Nothing leaves your computer.
- **Wake word + hotkey** — say "Computer" or press `Ctrl+Space` to activate.
- **16 built-in commands** — open apps, type text, press keys, file operations, web search, URLs, media control, volume, scripts, time/date, lock PC, screenshot.
- **Credential guard** — a standalone security layer that blocks passwords, API keys, tokens, and OTPs from reaching the executor. Tested with 22 security test cases.
- **Extensible** — add new commands without touching core logic via pattern registration.

## Quick Start

```powershell
# 1. Install Python 3.12+ from https://www.python.org/downloads/

# 2. Run the setup script
cd voice-assistant
.\setup.ps1

# 3. Launch the assistant
python -m src.main
```

First launch will download the Whisper model (~150MB). Say **"Computer"** or press **Ctrl+Space** then speak:

| Say | What happens |
|---|---|
| "open Chrome" | Launches Chrome |
| "type hello world" | Types into the active window |
| "search for Python tutorials" | Opens Google search |
| "volume up" | Increases volume |
| "lock my computer" | Locks the workstation |
| "take screenshot" | Captures and saves a screenshot |

## Project Structure

```
voice-assistant/
├── src/
│   ├── credential_guard.py      # Security filter — blocks credentials
│   ├── command_interpreter.py    # Rule-based intent parser
│   ├── action_executor.py        # Windows automation (pyautogui, etc.)
│   ├── stt_engine.py             # Speech-to-text (faster-whisper)
│   ├── tts_engine.py             # Text-to-speech (pyttsx3)
│   ├── wake_word.py              # Wake word + hotkey detector
│   └── main.py                   # Pipeline orchestrator
├── tests/
│   ├── test_credential_guard.py      # 22 security tests
│   └── test_command_interpreter.py   # 15 command parsing tests
├── commands/README.md           # Extension guide
├── config/assistant_config.json
├── setup.ps1                    # One-command setup
└── .gitignore
```

## Security

This assistant is built with a hard security boundary: **no credential material ever reaches the action executor**. The credential guard layer pattern-matches for passwords, API keys (OpenAI `sk-*`, GitHub `ghp_*`, AWS keys), JWTs, and OTPs before any command is dispatched. All 22 guard tests must pass.

## Tests

```powershell
python -m pytest tests/ -v
```

## Extending

See [commands/README.md](commands/README.md) for how to add new voice commands without modifying core security or pipeline code.
