"""Switch the collaboration mode for the person here (docs/milestones/M8_soul_presence.md A2).

open (default), jam, quiet, critique or museum. Quiet means no Soul block at all and no felt
notes; the person can always switch back by saying "open".
"""
import os
import sys
from pathlib import Path

DESCRIPTION = (
    "Switch the Soul's mode when the person asks: open (default), jam, quiet, critique, museum. Returns "
    'new and previous mode.'
)

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def run(mode):
    from iterbrow_runtime import soul_settings
    wanted = str(mode or "").strip().lower()
    if wanted == "museum night":
        wanted = "museum"
    if wanted not in soul_settings.MODES:
        return "ERROR: mode must be one of %s" % ", ".join(soul_settings.MODES)
    person = soul_settings.person()
    previous = soul_settings.mode()
    soul_settings.set_mode(person, wanted)
    return "MODE: %s (was %s)" % (wanted, previous)
