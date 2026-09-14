import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Run arbitrary JavaScript in the attached tab's page context and return its (JSON-serializable) return "
    "value. Use for reading page state, form values, computed styles, etc. that don't need a screenshot."
)


def run(expression):
    return call("eval", expression=expression)
