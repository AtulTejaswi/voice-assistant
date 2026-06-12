# Voice Assistant — Windows Setup Script

param($WakeWord = "computer")

Write-Host "=== Voice Assistant Setup ===" -ForegroundColor Cyan

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python not found. Install Python 3.12+ from python.org" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Python $($python.Version)" -ForegroundColor Green

Write-Host "Installing Python packages..." -ForegroundColor Cyan
$packages = @(
    "faster-whisper",
    "pyttsx3",
    "pyautogui",
    "keyboard",
    "sounddevice",
    "numpy",
    "pywinauto",
    "pytest"
)
foreach ($pkg in $packages) {
    Write-Host "  $pkg..." -ForegroundColor Gray
    python -m pip install $pkg --quiet
}

Write-Host "[OK] All packages installed" -ForegroundColor Green

Write-Host "Verifying installation..." -ForegroundColor Cyan
python -c "from faster_whisper import WhisperModel; from pyttsx3 import init; from pyautogui import typewrite; print('[OK] Core modules load successfully')"

Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Run: cd $PSScriptRoot; python -m src.main" -ForegroundColor White
Write-Host ""
Write-Host "Controls:" -ForegroundColor White
Write-Host "  Say '$WakeWord' to wake (or press Ctrl+Space)"
Write-Host "  Speak your command"
Write-Host "  Press Ctrl+C to quit"
