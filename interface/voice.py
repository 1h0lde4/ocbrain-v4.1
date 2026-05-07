"""
interface/voice.py — Local speech-to-text (Whisper) and TTS (pyttsx3).
Optional — disabled by default in settings.toml.
"""
import asyncio
import threading
from typing import Callable, Optional

from core.config import config

_tts_engine = None


def _get_tts():
    import logging
    log = logging.getLogger(__name__)
    global _tts_engine
    if _tts_engine is None:
        try:
            import pyttsx3
            _tts_engine = pyttsx3.init()
        except Exception as e:
            log.warning(f"[voice] Failed to initialize TTS engine: {e}")
    return _tts_engine


def speak(text: str):
    engine = _get_tts()
    if engine:
        engine.say(text)
        engine.runAndWait()


def listen_once() -> Optional[str]:
    """
    Record audio until silence, then transcribe with Whisper.
    Returns transcribed text or None on failure.
    """
    try:
        import tempfile
        import sounddevice as sd
        import soundfile as sf
        import whisper
        import numpy as np

        sample_rate = 16000
        duration    = 5   # seconds — extend with VAD in future
        print("[voice] Listening...")
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()
        audio = audio.flatten()

        # Silence detection — skip if too quiet
        if np.abs(audio).mean() < 0.01:
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            model  = whisper.load_model("base")
            result = model.transcribe(f.name)
            return result.get("text", "").strip()

    except ImportError:
        print("[voice] sounddevice/soundfile/whisper not installed.")
        return None
    except Exception as e:
        print(f"[voice] listen error: {e}")
        return None


def start_hotkey_listener(on_query: Callable[[str], None]):
    """
    Background thread: listens for hotkey (Ctrl+Shift+Space),
    records voice query, calls on_query with transcribed text.
    """
    if not config.get("global.voice_enabled", False):
        return

    try:
        import keyboard

        def _on_hotkey():
            text = listen_once()
            if text:
                print(f"[voice] Heard: {text}")
                on_query(text)

        keyboard.add_hotkey("ctrl+shift+space", _on_hotkey)
        print("[voice] Hotkey listener started (Ctrl+Shift+Space).")

    except ImportError:
        print("[voice] 'keyboard' package not installed — hotkey listener disabled.")


def start(on_query: Callable[[str], None]):
    t = threading.Thread(
        target=start_hotkey_listener,
        args=(on_query,),
        daemon=True,
    )
    t.start()
