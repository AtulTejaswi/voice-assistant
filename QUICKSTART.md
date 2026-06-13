# JARVIS Quickstart (100% Free)

## Step 1 — Install Ollama
Download from https://ollama.com and install.
Then open a terminal and run:
    ollama pull llama3.2:3b

## Step 2 — Install Python dependencies
Run setup.ps1 (Windows) or:
    pip install faster-whisper sounddevice pyttsx3 pyautogui keyboard psutil pyperclip duckduckgo-search

## Step 3 — Start Ollama
In a separate terminal window, run:
    ollama serve

## Step 4 — Run JARVIS
    python -m src.main

## Troubleshooting
- "JARVIS says hello and closes" → Ollama isn't running. Run `ollama serve` first.
- "I had trouble processing that" → LLM call failed. Check Ollama is running and model is pulled.
- Wake word not triggering → Say "Computer" clearly, or press Ctrl+Space.
- No microphone → Run `python -m sounddevice` to list devices.
- Slow responses → Switch to a smaller model: change "llama3.2:3b" to "tinyllama" in config.
