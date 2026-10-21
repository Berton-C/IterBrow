"""Undo Iter's own changes to an app in the person's vault (docs/milestones/M14_vault_and_foundry_loop.md B2).

Every write_file/edit_file inside vault/<app>/ saves the previous content first (iterbrow_runtime/vault.py
snapshot); this restores the newest ones, newest first. steps="0" shows the history and changes nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    'Undo your last change(s) to vault/<app>/ (every write there saved the previous content). steps: how '
    'many, newest first (default 1); steps="0" lists the history and changes nothing. Then app_probe '
    'again.'
)

HISTORY_LINES = 20


def run(app, steps="1"):
    vault = _files.vault_dir()
    if vault is None:
        return _files.refused(_files.NO_VAULT)
    from iterbrow_runtime import vault as store
    app = str(app or "").strip()
    try:
        count = int(str(steps if steps is not None else "1").strip() or "1")
    except ValueError:
        return _files.input_error("ERROR: steps is a number (0 lists the history)")
    if count < 0:
        return _files.input_error("ERROR: steps is 0 or more")
    if not store.APP_ID.match(app) or (store.app_dir(app, vault) is None and not store.entries(vault, app)):
        return _files.input_error("ERROR: no app named %r in the apps folder (vault/)" % app)
    if count == 0:
        items = store.history(app, vault)
        if not items:
            return "%s: no changes recorded" % app
        lines = ["%s: %d change%s" % (app, len(items), "" if len(items) == 1 else "s")]
        for item in items[:HISTORY_LINES]:
            size = "new" if item.get("bytes") is None else "{:,} bytes".format(item["bytes"])
            lines.append("%s %s %s (%s)" % (store._second(item["at"]), item.get("reason", "?"), item["file"], size))
        if len(items) > HISTORY_LINES:
            lines.append("… and %d older" % (len(items) - HISTORY_LINES))
        return "\n".join(lines)
    done = store.rollback(app, count, vault)
    if not done:
        return "NOTHING TO ROLL BACK: %s" % app
    return "\n".join("ROLLED BACK %s: %s (%s)" % (app, item["file"], "deleted" if item.get("deleted") else "to " + item["restored_from"])
                     for item in done)
