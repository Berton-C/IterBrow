import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser_bridge import call

DESCRIPTION = (
    "Open one of the person's apps (id from apps) as they see it: an app tab with window.iterApp. If "
    'open, focuses it and reloads when its files changed. Waits for the load and makes it your target. '
    'Use after every edit, before app_probe or clicking.'
)


def building(app):
    """M15-C: an app in the person's apps folder is one Iter builds; its opens and probes keep a ledger."""
    try:
        from iterbrow_runtime import vault
        return vault.APP_ID.match(app) is not None and vault.app_dir(app) is not None
    except Exception:
        return False


def ledger_line(app, check, observe):
    """`· ledger: …` from this observation (M15-C4); a ledger failure never fails the tool."""
    if not check:
        return " · ledger: no check (the tab is locked or the page did not answer)"
    try:
        return " · ledger: " + observe()
    except Exception as error:
        print("[build ledger] %s: %s: %s" % (app, type(error).__name__, error))
        return " · ledger: not recorded (%s)" % type(error).__name__


def run(app_id):
    app = str(app_id).strip()
    params = {"appId": app}
    built = building(app)
    if built:  # M15-C1: the contract check looks for what the ask named
        try:
            from iterbrow_runtime import build_ledger
            params.update(check=True, selectors=build_ledger.asked(app))
        except Exception:
            params.update(check=True, selectors=[])
    result = call("openApp", **params)
    how = "reloaded (files changed since it loaded)" if result.get("reloaded") else ("focused" if result.get("focused") else "opened")
    text = "app %s: tabId=%s %s %s" % (result.get("appId") or app_id, result.get("tabId"), how, result.get("url") or "")
    if built:
        from iterbrow_runtime import build_ledger
        # facts_from_check: what the running page shows, observed now (build_ledger.observe_open).
        text += ledger_line(app, result.get("check"), lambda: build_ledger.observe_open(app, result.get("check")))
    return text
