"""Manimo's built-in narration voice: Kokoro (82M), running on this PC with no key and no internet.

A `KokoroVoice` is a ManimGX voice (a callable from text to a Speech), so `self.say("...")` works with it. Audio is kept
in a cache folder named by voice, speed and text, so a line is only spoken once.

Model files (kokoro-v1.0.int8.onnx, voices-v1.0.bin) come from the kokoro-onnx project's model-files-v1.0 release and
sit in app\\models (or %LOCALAPPDATA%\\Manimo\\data\\kokoro).
"""
import hashlib
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Manimo" / "data"
CACHE_DIR = DATA_DIR / "voice-cache"
MODEL_NAME = "kokoro-v1.0.int8.onnx"
VOICES_NAME = "voices-v1.0.bin"
SAMPLE_RATE = 24000

# id -> (label, accent, note, gender); the first one is the default. Curated from Kokoro's English voices for teaching:
# clear, even pace, easy to follow at 0.9x to 1.1x speed. The other voices in the model file are left out on purpose.
VOICES = {
    "am_adam": ("Adam", "American", "Deep, steady male voice", "male"),
    "am_echo": ("Echo", "American", "Clear, friendly male voice", "male"),
    "am_michael": ("Michael", "American", "Confident, clear male voice", "male"),
    "am_eric": ("Eric", "American", "Even, patient male voice", "male"),
    "bm_lewis": ("Lewis", "British", "Warm British male voice", "male"),
    "bm_george": ("George", "British", "Authoritative British male voice", "male"),
    "bm_daniel": ("Daniel", "British", "Calm British male voice", "male"),
    "af_nicole": ("Nicole", "American", "Soft, calm female voice", "female"),
    "af_heart": ("Heart", "American", "Warm, natural female voice", "female"),
    "af_bella": ("Bella", "American", "Bright, expressive female voice", "female"),
    "af_sarah": ("Sarah", "American", "Clear, friendly female voice", "female"),
    "af_sky": ("Sky", "American", "Light, youthful female voice", "female"),
    "bf_emma": ("Emma", "British", "Clear British female voice", "female"),
    "bf_isabella": ("Isabella", "British", "Warm British female voice", "female"),
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
            "voices": [{"id": k, "label": v[0], "accent": v[1], "note": v[2], "gender": v[3]} for k, v in VOICES.items()]}


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


# ---------------------------------------------------------------- how words are pronounced, and per-scene voice settings
# Kept as plain comment lines in the lesson's file, so they travel with it:
#   # say: sin = sine          (anywhere in the file: say "sine" wherever "sin" is written)
#   # say-defaults: off        (do not use the built-in list below)
#   # voice: bf_emma           (in the comment lines directly above a scene class)
#   # speed: 1.1
SAY_LINE = re.compile(r"^[ \t]*#[ \t]*say:[ \t]*(.+?)[ \t]*=[ \t]*(.+?)[ \t]*$", re.M)
DEFAULTS_OFF = re.compile(r"^[ \t]*#[ \t]*say-defaults:[ \t]*off\b", re.M | re.I)
BUILTIN_PRON = [
    ("kΩ", "kilo ohms"), ("MΩ", "mega ohms"), ("Ω", "ohms"), ("μF", "microfarads"), ("µF", "microfarads"), ("°C", "degrees Celsius"),
    ("°", " degrees"), ("ΔV", "delta V"), ("Δ", "delta "), ("π", "pi"), ("θ", "theta"), ("μ", "mu"), ("µ", "mu"), ("ω", "omega"), ("λ", "lambda"),
    ("α", "alpha"), ("β", "beta"), ("γ", "gamma"), ("ε", "epsilon"), ("ρ", "rho"), ("σ", "sigma"), ("τ", "tau"), ("φ", "phi"),
    ("±", "plus or minus"), ("≈", "approximately"), ("≠", "not equal to"), ("≤", "less than or equal to"), ("≥", "greater than or equal to"),
    ("×", "times"), ("÷", "divided by"), ("→", "gives"), ("√", "square root of "), ("∞", "infinity"), ("²", " squared"), ("³", " cubed"),
    ("sin", "sine"), ("cos", "cosine"), ("tan", "tangent"),
]
_rules = []             # (compiled pattern, replacement), in the order they are applied
_rules_key = ""


def _rule(a, b):
    pat = re.escape(a)
    if re.match(r"[A-Za-z0-9_]", a[:1]):          # a plain word is matched as a whole word; symbols such as 2π or x² are matched anywhere
        pat = r"(?<![A-Za-z0-9_])" + pat
    if re.match(r"[A-Za-z0-9_]", a[-1:]):
        pat += r"(?![A-Za-z0-9_])"
    if not re.match(r"[A-Za-z0-9_]", a[:1]):                 # a symbol stands apart from its neighbours when spoken: 2π is "2 pi"
        b = " " + b.strip() + " "
    return re.compile(pat), b


def set_pronunciations(pairs, defaults=True):
    """Use these (written, spoken) pairs, then the built-in ones, for every line spoken from now on."""
    global _rules, _rules_key
    pairs = [(str(a), str(b)) for a, b in pairs if str(a).strip()]
    _rules = [_rule(a, b) for a, b in pairs + (BUILTIN_PRON if defaults else [])]
    _rules_key = hashlib.sha1(repr((pairs, bool(defaults))).encode("utf-8")).hexdigest()[:8] if (pairs or not defaults) else ""


def pronounce(text):
    """The words as they should be spoken (the text on screen is not changed)."""
    for pat, rep in _rules:
        text = pat.sub(rep, text)
    return re.sub(r"\s+([.,;:!?])", r"\1", " ".join(text.split()))      # no stray space before punctuation


def annotations(code, scene=None):
    """What the file says about speech: pronunciations, and the voice and speed set for `scene` in the comments above its class."""
    code = code or ""
    out = {"pron": [(a.strip(), b.strip()) for a, b in SAY_LINE.findall(code)], "defaults": not DEFAULTS_OFF.search(code), "voice": None, "speed": None}
    if scene:
        m = re.search(r"^class[ \t]+" + re.escape(scene) + r"\b", code, re.M)
        if m:
            above = code[:m.start()].split("\n")[:-1]
            while above and above[-1].lstrip().startswith("#"):
                line = above.pop().strip().lstrip("#").strip()
                k = re.match(r"(voice|speed)\s*:\s*(\S+)", line, re.I)
                if k and k.group(1).lower() == "voice" and k.group(2) in VOICES and out["voice"] is None:
                    out["voice"] = k.group(2)
                elif k and k.group(1).lower() == "speed" and out["speed"] is None:
                    try:
                        out["speed"] = float(k.group(2))
                    except ValueError:
                        pass
    return out


def source_and_scene(argv):
    """The code file and the scene named in manimgx arguments (`render file.py Scene ...`), when both are there."""
    for i, a in enumerate(argv):
        if a.lower().endswith(".py") and os.path.isfile(a):
            nxt = argv[i + 1] if i + 1 < len(argv) else ""
            return a, (nxt if nxt and not nxt.startswith("-") else None)
    return None, None


def configure(code, scene, name, speed):
    """Apply a file's pronunciations and the scene's own voice and speed. Returns the (voice, speed) to use."""
    a = annotations(code, scene)
    set_pronunciations(a["pron"], a["defaults"])
    return _clean(a["voice"] or name, a["speed"] if a["speed"] is not None else speed)


def speak(text, name=DEFAULT_VOICE, speed=1.0):
    """Returns the path of a wav file saying `text` (made once, then reused)."""
    name, speed = _clean(name, speed)
    text = pronounce(" ".join(str(text).split()))
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
    pron: str = ""                     # names the pronunciation list in use, so a changed list speaks the line again

    def __call__(self, text):
        from manimgx.audio import Speech
        return Speech(speak(text, self.name, self.speed).read_bytes(), text=text)
