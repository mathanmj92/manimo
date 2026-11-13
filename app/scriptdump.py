"""Lists what a ManimGX scene says and when, without rendering.

Usage: python scriptdump.py scene.py SceneName [voice speed]     (prints one JSON object)

Each self.say(...) asks the scene's voice for a Speech. When Manimo's narration voice is installed it speaks the lines
(kept in a cache, so this is quick the second time) and the times are real. Otherwise the voice is replaced by silence
of an estimated length (about 0.35 s a word) and the times are estimates.
"""
import importlib.util
import json
import os
import sys

PER_WORD = 0.35
PAD = 0.4
RATE = 8000


def main():
    path, name = sys.argv[1], sys.argv[2]
    vname = sys.argv[3] if len(sys.argv) > 3 else "am_adam"
    vspeed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import manimgx as m
    from manimgx.audio import Speech
    import numpy as np
    import voice

    real = voice.available()
    with open(path, encoding="utf-8") as fh:
        vname, vspeed = voice.configure(fh.read(), name, vname, vspeed)        # the file's pronunciations, and this scene's own voice and speed
    narrator = voice.KokoroVoice(vname, vspeed, voice._rules_key) if real else None
    lines = []

    def speech(self, text, voice=None):
        if narrator is not None:
            sp = narrator(text)
            dur = float(sp.duration)
        else:
            dur = PER_WORD * max(1, len(text.split())) + PAD
            sp = Speech(np.zeros(int(RATE * dur), dtype="float32"), text=text, rate=RATE)
        lines.append({"t": round(float(self.time), 2), "text": " ".join(text.split()), "dur": round(dur, 2)})
        return sp

    m.Scene.speech = speech
    real_say = m.Scene.say

    def say(self, script, *animations, **kw):
        own = [float(a.run_time) for a in animations]            # how long the animations were written to take, before say stretches them to the speech
        out = real_say(self, script, *animations, **kw)
        if lines:
            lines[-1]["anim"] = round(max(own), 2) if own else None
        return out
    m.Scene.say = say
    voice.add_compat(m)
    spec = importlib.util.spec_from_file_location("userscene", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    scene = getattr(mod, name)()
    scene.construct()
    print(json.dumps({"lines": lines, "end": round(float(scene.time), 2), "estimated": not real, "voice": vname, "speed": vspeed}))


try:
    main()
except SystemExit:
    raise
except BaseException as e:
    print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}))
