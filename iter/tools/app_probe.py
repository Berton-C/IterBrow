import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser_bridge import call, refused
from iterbrow_runtime.tool_results import ToolOutput

DESCRIPTION = (
    "Prove an open app works: run steps (JSON list of {kind: click|fill, selector, value?}) then check assertions "
    "(JSON list of {kind: text|value|count|visible, selector, expected}) in the app's tab. First line: PROBE <app>: "
    "<n> passed, <m> failed; then one line per assertion. Open the app first with browser_open_app. timeout: seconds."
)


def _shown(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "nothing"
    return repr(value) if isinstance(value, str) else str(value)


def _list(text, name):
    value = json.loads(text) if isinstance(text, str) else text
    if not isinstance(value, list):
        raise ValueError("%s must be a JSON list" % name)
    return value


def run(app, assertions, steps="[]", timeout="3"):
    try:
        steps_list = _list(steps or "[]", "steps")
        assertions_list = _list(assertions, "assertions")
        timeout_ms = int(float(str(timeout or "3")) * 1000)
    except (ValueError, TypeError) as error:
        return ToolOutput("ERROR: %s (steps and assertions are JSON lists; timeout is seconds)" % error, None, state="invalid_input")
    result = call("probe", appId=str(app).strip(), steps=steps_list, assertions=assertions_list, timeoutMs=timeout_ms)
    if refused(result):
        return result
    lines = ["PROBE %s: %d passed, %d failed" % (app, result.get("passed", 0), result.get("failed", 0))]
    for item in result.get("observations") or []:
        lines.append("%s %s %s: expected %s got %s" % ("✓" if item.get("passed") else "✗", item.get("kind"), item.get("selector"),
                                                     _shown(item.get("expected")), _shown(item.get("actual"))))
    lines.append("ready=%s" % ("true" if result.get("ready") else "false (the app has not set data-iter-ready; fine for a plain app)"))
    return "\n".join(lines)
