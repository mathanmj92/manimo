"""Manimo's built-in narration voice: Kokoro (82M), running on this PC with no key and no internet.

A `KokoroVoice` is a ManimGX voice (a callable from text to a Speech), so `self.say("...")` works with it. Audio is kept
in a cache folder named by voice, speed and text, so a line is only spoken once.

Model files (kokoro-v1.0.int8.onnx, voices-v1.0.bin) come from the kokoro-onnx project's model-files-v1.0 release and
sit in app\\models (or %LOCALAPPDATA%\\Manimo\\data\\kokoro).
"""
import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
CACHE_DIR = DATA_DIR / "voice-cache"
MODEL_NAME = "kokoro-v1.0.int8.onnx"
VOICES_NAME = "voices-v1.0.bin"
SAMPLE_RATE = 24000

# id -> (label, accent, note); the first one is the default
VOICES = {
    "am_adam": ("Adam", "American", "Deep, steady male voice"),
    "am_echo": ("Echo", "American", "Clear, friendly male voice"),
    "af_nicole": ("Nicole", "American", "Soft, calm female voice"),
    "bm_lewis": ("Lewis", "British", "Warm British male voice"),
}
DEFAULT_VOICE = "am_adam"
_lock = threading.Lock()
_engine = None


def model_paths():
    for folder in (APP_DIR / "models", DATA_DIR / "kokoro"):
        m, v = folder / MODEL_NAME, folder / VOICES_NAME
        if m.is_file() and v.is_file():
            return m, v
    return None


def available():
    if model_paths() is None:
        return False
    try:
        import kokoro_onnx  # noqa: F401
        import numpy  # noqa: F401
        import soundfile  # noqa: F401
    except Exception:
        return False
    return True


def status():
    return {"available": available(), "default": DEFAULT_VOICE,
            "voices": [{"id": k, "label": v[0], "accent": v[1], "note": v[2]} for k, v in VOICES.items()]}


def _kokoro():
    global _engine
    if _engine is None:
        from kokoro_onnx import Kokoro
        m, v = model_paths()
        _engine = Kokoro(str(m), str(v))
    return _engine


def _clean(name, speed):
    name = name if name in VOICES else DEFAULT_VOICE
    try:
        speed = min(1.4, max(0.7, float(speed)))
    except (TypeError, ValueError):
        speed = 1.0
    return name, round(speed, 2)


def speak(text, name=DEFAULT_VOICE, speed=1.0):
    """Returns the path of a wav file saying `text` (made once, then reused)."""
    name, speed = _clean(name, speed)
    text = " ".join(str(text).split())
    if not text:
        raise ValueError("There is nothing to say.")
    key = hashlib.sha1(f"{name}|{speed}|{text}".encode("utf-8")).hexdigest()[:20]
    out = CACHE_DIR / f"{name}-{key}.wav"
    if out.is_file() and out.stat().st_size > 1000:
        return out
    import soundfile as sf
    with _lock:                       # one sentence at a time keeps memory and CPU steady
        samples, rate = _kokoro().create(text, voice=name, speed=speed, lang="en-gb" if name.startswith("b") else "en-us")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    sf.write(str(tmp), samples, rate, format="WAV", subtype="PCM_16")
    os.replace(tmp, out)
    return out


def add_compat(m):
    """Teach ManimGX scenes the `with self.voiceover(text=...) as tracker:` block of the manim-voiceover plugin, which
    is how most narrated Manim code is written. The line is spoken while the block's animations play, and the block
    lasts at least as long as the speech; `tracker.duration` is the speech's length in seconds."""
    from contextlib import contextmanager

    class Tracker:
        def __init__(self, duration, text):
            self.duration, self.text = duration, text

    @contextmanager
    def voiceover(self, text=None, **_ignored):
        if not text or not str(text).strip():
            raise ValueError('voiceover needs the words to say: with self.voiceover(text="...")')
        speech = self.speech(str(text))
        self.add_sound(speech)
        start = self.time
        yield Tracker(float(speech.duration), str(text))
        left = float(speech.duration) - (float(self.time) - float(start))
        if left > 0:
            self.wait(left)

    if not hasattr(m.Scene, "voiceover"):
        m.Scene.voiceover = voiceover
        plain_wait = m.Scene.wait

        def wait(self, duration=1.0, *args, **kwargs):      # `wait(tracker.duration - 3)` is common and can go below zero
            try:
                if duration < 0:
                    duration = 0.0
            except TypeError:
                pass
            return plain_wait(self, duration, *args, **kwargs)
        m.Scene.wait = wait


@dataclass(frozen=True)
class KokoroVoice:
    """A ManimGX voice. Its fields name it in ManimGX's own cache, so changing the voice or speed speaks the line again."""
    name: str = DEFAULT_VOICE
    speed: float = 1.0

    def __call__(self, text):
        from manimgx.audio import Speech
        return Speech(speak(text, self.name, self.speed).read_bytes(), text=text)
