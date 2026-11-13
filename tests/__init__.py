"""Shared setup: put app/ on sys.path so tests can import server and project, and keep every test away from the real Manimo data folder."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

# Modules work out their data folder from %LOCALAPPDATA% when they are imported. Point it at a throw-away folder first, so no test can read or
# write the real settings, saved fixes, usage, brand or history of whoever runs the tests.
_SANDBOX = tempfile.mkdtemp(prefix="manimo-tests-")
os.environ["LOCALAPPDATA"] = _SANDBOX
