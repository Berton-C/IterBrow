import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call, named

DESCRIPTION = (
    "Wait until something is true in a tab: a CSS selector matches a visible element, the page shows some text, "
    "and/or the URL contains a string (every one you give must hold). timeout in seconds (default 10, at most 30). "
    "Use after a click or load before you check the result. tab_id: optional (default: the target tab)."
)


def run(selector="", text="", url="", timeout="10", tab_id=""):
    params = {"tabId": int(tab_id)} if str(tab_id or "").strip() else {}
    for key, value in (("selector", selector), ("text", text), ("url", url)):
        if str(value or "").strip():
            params[key] = str(value)
    if not any(key in params for key in ("selector", "text", "url")):
        raise ValueError("give at least one of selector, text, url")
    params["timeoutMs"] = int(float(str(timeout or "10")) * 1000)
    result = call("waitFor", **params)
    match = result.get("match")
    what = named(match) if isinstance(match, dict) else repr(match) if match else "it"
    return "found %s after %s ms" % (what, result.get("afterMs"))
