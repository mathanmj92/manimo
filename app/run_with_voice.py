"""Runs the manimgx command line with Manimo's narration voice as every scene's default voice.

Usage: python run_with_voice.py [--voice am_adam] [--speed 1.0] <manimgx arguments...>

A scene that sets its own `voice` keeps it. Scenes that never call self.say are not affected.
"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
name, speed = "am_adam", 1.0
while args and args[0] in ("--voice", "--speed") and len(args) >= 2:
    if args[0] == "--voice":
        name = args[1]
    else:
        try:
            speed = float(args[1])
        except ValueError:
            pass
    args = args[2:]

import manimgx as m  # noqa: E402
import voice  # noqa: E402

voice.add_compat(m)
if voice.available():
    name = name if name in voice.VOICES else voice.DEFAULT_VOICE
    m.Scene.voice = voice.KokoroVoice(name, voice._clean(name, speed)[1])
sys.argv = ["manimgx"] + args
runpy.run_module("manimgx", run_name="__main__", alter_sys=True)
