import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser_bridge import call, refused
from iterbrow_runtime.tool_results import ToolOutput

DESCRIPTION = (
    'Prove an open app works: run steps, then check assertions in its tab. steps: JSON [{kind: '
    'click|fill, selector, value?}]; assertions: JSON [{kind: text|value|count|visible, selector, '
    'expected}]; none: its probe.json. First line: PROBE <app>: n passed, m failed.'
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


def _invalid(message):
    return ToolOutput(message, None, state="invalid_input")


def _app_spec(app):
    """(spec dict, shown path) from the app's probe.json, (None, shown path) when it has none, or raises ValueError.

    M14-C3: a vault app (vault/<id>/probe.json) first, then a plain app of iter/ (<id>/probe.json)."""
    from iterbrow_runtime import soul_briefs, vault
    root = vault.iter_root()
    folder = soul_briefs.app_folder(root, app) if vault.APP_ID.match(app) else None
    if folder is None:
        return None, None
    home = vault.path(vault.settings_file(root))
    shown = ("vault/%s/probe.json" % app) if home and Path(folder).parent == home else "%s/probe.json" % app
    spec_file = Path(folder) / "probe.json"
    if not spec_file.is_file() or spec_file.is_symlink():
        return None, shown
    try:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("%s is not valid JSON (%s)" % (shown, error))
    if not isinstance(spec, dict) or not isinstance(spec.get("assertions"), list) or not isinstance(spec.get("steps", []), list):
        raise ValueError("%s must be {\"steps\": [...], \"assertions\": [...]}" % shown)
    return spec, shown


def run(app, steps="", assertions="", timeout=""):
    app = str(app or "").strip()
    source = ""
    try:
        if str(assertions or "").strip():
            steps_list = _list(steps or "[]", "steps")
            assertions_list = _list(assertions, "assertions")
        else:
            spec, shown = _app_spec(app)
            if spec is None:
                return _invalid("ERROR: no assertions given and %s is missing" % (shown or ("an app named %r" % app)))
            steps_list, assertions_list, source = spec.get("steps", []), spec["assertions"], " (probe.json)"
        timeout_ms = int(float(str(timeout or "3")) * 1000)
    except (ValueError, TypeError) as error:
        return _invalid("ERROR: %s (steps and assertions are JSON lists; timeout is seconds)" % error)
    from browser_open_app import building
    built = building(app)
    extra = {}
    if built:  # M15-C1: the contract check runs before the steps
        try:
            from iterbrow_runtime import build_ledger
            extra = {"check": True, "selectors": build_ledger.asked(app)}
        except Exception:
            extra = {"check": True, "selectors": []}
    result = call("probe", appId=app, steps=steps_list, assertions=assertions_list, timeoutMs=timeout_ms, **extra)
    if refused(result):
        return result
    lines = ["PROBE %s%s: %d passed, %d failed" % (app, source, result.get("passed", 0), result.get("failed", 0))]
    for item in result.get("observations") or []:
        lines.append("%s %s %s: expected %s got %s" % ("✓" if item.get("passed") else "✗", item.get("kind"), item.get("selector"),
                                                     _shown(item.get("expected")), _shown(item.get("actual"))))
    lines.append("ready=%s" % ("true" if result.get("ready") else "false (the app has not set data-iter-ready; fine for a plain app)"))
    if built:
        # M15-C2/C4: the run and its check become facts (facts_from_probe); the ledger line comes from them,
        # "not recorded" when the store could not take them. Never a failure of the probe itself.
        from iterbrow_runtime import build_ledger
        probe_json = {"steps": steps_list, "assertions": assertions_list}
        try:
            lines.append("· ledger: " + build_ledger.observe_probe(app, result, probe_json))
        except Exception as error:
            print("[build ledger] %s: %s: %s" % (app, type(error).__name__, error))
            lines.append("· ledger: not recorded (%s)" % type(error).__name__)
    return "\n".join(lines)
