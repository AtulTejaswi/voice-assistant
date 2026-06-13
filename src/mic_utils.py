"""
Microphone utilities — device auto-detection, format conversion, downsampling.
"""

from typing import Optional
import numpy as np
import sounddevice as sd


# Cached best device info
_best_device: Optional[dict] = None


def find_best_device() -> dict:
    """Auto-detect the best microphone device quickly.

    Checks a shortlist of likely devices (Microphone Array, front panel,
    default input) and picks the first one that returns real audio signal.
    Falls back to the system default input device.
    """
    global _best_device
    if _best_device is not None:
        return _best_device

    devices = sd.query_devices()

    # Build shortlist of candidate indices
    shortlist = []
    for idx, info in enumerate(devices):
        if info["max_input_channels"] == 0:
            continue
        name = info["name"].lower()
        sr = int(info["default_samplerate"])
        # Skip known non-mic devices
        if any(kw in name for kw in ["speaker", "stereo mix", "output", "bluetooth"]):
            continue
        # Prefer mic array / front panel / microphone
        score = 0
        if "microphone array" in name or "mic array" in name:
            score = 3
        elif "microphone" in name or "mic in" in name or "front panel" in name:
            score = 2
        elif "input" in name:
            score = 1
        shortlist.append((score, idx, info["name"], sr))

    # Sort by score descending
    shortlist.sort(reverse=True)

    # Try each candidate briefly
    for score, idx, name, sr in shortlist:
        for dtype in [np.int16, np.float32]:
            try:
                rec = sd.rec(int(0.3 * sr), samplerate=sr, channels=1, dtype=dtype, device=idx)
                sd.wait()
                if dtype == np.int16:
                    data = rec.flatten().astype(np.float32) / 32768.0
                else:
                    data = rec.flatten()
                rms = np.sqrt(np.mean(data ** 2))
                if np.isfinite(rms) and rms > 0.0003:
                    _best_device = {"index": idx, "name": name, "samplerate": sr, "dtype": dtype}
                    print(f"[Mic] Selected: [{idx}] {name} @ {sr}Hz ({dtype.__name__})")
                    return _best_device
                break
            except Exception:
                continue

    # Fallback: default input device
    default_idx = sd.default.device[0] if isinstance(sd.default.device, tuple) else sd.default.device
    if default_idx is None:
        default_idx = 0
    info = sd.query_devices(default_idx)
    sr = int(info["default_samplerate"])
    _best_device = {"index": default_idx, "name": info["name"], "samplerate": sr, "dtype": np.int16}
    print(f"[Mic] Fallback: [{default_idx}] {info['name']} @ {sr}Hz int16")
    return _best_device


def resample_to_16k(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """Simple linear interpolation resampling to 16000 Hz."""
    if orig_sr == 16000:
        return audio
    target_len = int(len(audio) * 16000 / orig_sr)
    indices = np.linspace(0, len(audio) - 1, target_len)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def convert_to_float(audio: np.ndarray, dtype: np.dtype) -> np.ndarray:
    """Convert int16/int32 array to float32 in [-1, 1] range."""
    if dtype == np.int16:
        return audio.astype(np.float32) / 32768.0
    elif dtype == np.int32:
        return audio.astype(np.float32) / 2147483648.0
    return audio.astype(np.float32)
