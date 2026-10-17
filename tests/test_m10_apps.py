#!/usr/bin/env python3
"""M10-C1..C6: every local app in the fold — the catalog, the Apps button, plain apps as app tabs,
external links leaving the app, focus-not-clutter, and the `apps` tool.

Spec: docs/milestones/M10_ally_sdk.md section C.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m10_support import (pending, m10_root, require_m10, write_soul_settings, make_app_dir, tab_manager_with_fake_electron,  # noqa: E402
                         toolbar_page_script, TOOLBAR_API, run_playwright, playwright_available, node, NODE, REPO, ITER_SRC)
from test_m7_brief import make_project  # noqa: E402


def catalog(root):
    proc = subprocess.run([sys.executable, "-m", "iterbrow_runtime.local_apps"], cwd=str(ITER_SRC),
                          env=dict(os.environ, ITER_DIR=str(root), PYTHONPATH=str(ITER_SRC)), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


class CatalogTests(unittest.TestCase):
    """M10-C1"""

    @pending("M10-C1")
    def test_foundry_and_plain_apps_in_one_sorted_list(self):
        require_m10()
        temp = tempfile.mkdtemp(prefix="m10cat-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        make_app_dir(temp, "mapstation")
        make_app_dir(temp, "nodequest")
        (Path(temp) / "nodequest" / "brief.json").write_text(json.dumps({"for": "a learner", "flourishing": "curious", "by": "berton", "at": 1}))
        (Path(temp) / "music").mkdir()  # no index.html: not an app
        (Path(temp) / ".hidden").mkdir(); (Path(temp) / ".hidden" / "index.html").write_text("x")
        (Path(temp) / "node_modules").mkdir(); (Path(temp) / "node_modules" / "index.html").write_text("x")
        os.symlink(str(Path(temp) / "mapstation"), str(Path(temp) / "linked"))
        make_project(temp, "orbit")
        apps = catalog(temp)
        self.assertEqual([a["id"] for a in apps], ["mapstation", "nodequest", "orbit"])
        by_id = {a["id"]: a for a in apps}
        self.assertEqual(by_id["mapstation"]["kind"], "plain")
        self.assertEqual(by_id["mapstation"]["entry"], "index.html")
        self.assertIsNone(by_id["mapstation"]["brief"])
        self.assertEqual(by_id["nodequest"]["brief"]["for"], "a learner")
        self.assertEqual(by_id["orbit"]["kind"], "foundry")
        self.assertEqual(by_id["orbit"]["path"], str(Path(temp) / "apps" / "orbit"))
        self.assertEqual(by_id["mapstation"]["path"], str(Path(temp) / "mapstation"))

    @pending("M10-C1")
    def test_main_reads_the_catalog_through_one_ipc(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        self.assertIn("ipcMain.handle('apps:catalog'", main)
        self.assertIn("iterbrow_runtime.local_apps", main)
        self.assertIn("ipcMain.handle('apps:menu'", main)
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        for name in ("appsCatalog", "appsMenu"):
            self.assertIn(name, preload, name)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class AppsButtonTests(unittest.TestCase):
    """M10-C2"""

    @pending("M10-C2")
    def test_button_sits_next_to_crm_and_asks_for_the_menu(self):
        require_m10()
        out = json.loads(run_playwright(toolbar_page_script("document.querySelector('#btn-apps').click();", """(() => {
const crm = document.querySelector('#btn-crm'); const apps = document.querySelector('#btn-apps');
return { exists: !!apps, label: apps && apps.textContent.trim(), after: crm && apps && crm.nextElementSibling === apps,
         calls: window.__calls.filter((c) => c[0].startsWith('apps')) };
})()""", TOOLBAR_API)).strip().splitlines()[-1])
        self.assertTrue(out["exists"])
        self.assertEqual(out["label"], "Apps")
        self.assertTrue(out["after"], "Apps sits right after CRM")
        self.assertEqual(out["calls"], [["appsMenu"]])

    @pending("M10-C2")
    def test_menu_template_lists_every_app_with_its_brief(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        self.assertIn("function appsMenuTemplate", main)
        code, stdout, stderr = node("""
const Module = require('module'); const realLoad = Module._load;
Module._load = function (request, ...rest) { if (request === 'electron') return new Proxy({}, { get: () => ({}) }); return realLoad.call(this, request, ...rest); };
const src = require('fs').readFileSync(%s, 'utf8');
const start = src.indexOf('function appsMenuTemplate'); const end = src.indexOf('\\n}\\n', start) + 3;
const fn = new Function(src.slice(start, end) + '; return appsMenuTemplate;')();
const t = fn([{ id: 'orbit', kind: 'foundry', brief: { for: 'Bright' } }, { id: 'mapstation', kind: 'plain', brief: null }], (id) => id);
process.stdout.write(JSON.stringify(t.map((i) => [i.label, typeof i.click])));
""" % json.dumps(str(REPO / "main.js")))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout.strip().splitlines()[-1]), [["orbit — for Bright", "function"], ["mapstation", "function"]])


@unittest.skipUnless(NODE, "needs node")
class TabTests(unittest.TestCase):
    """M10-C3..C5: plain apps as app tabs, external links, findTab and focus."""

    def _run(self, body):
        code, stdout, stderr = node(tab_manager_with_fake_electron() + body)
        self.assertEqual(code, 0, stderr)
        return json.loads(stdout.strip().splitlines()[-1])

    @pending("M10-C5")
    def test_find_tab_and_focus(self):
        require_m10()
        out = self._run("""
const tabs = new TabManager(win, { getContentBounds: bounds, pwqPath: '/x/pwq.html' });
const a = tabs.createTab('https://a.test/');
const crm = tabs.createTab('file:///x/crm/index.html', { preload: '/p.js', restrictNavigation: true, appId: 'crm', consumerId: 'crm-ui' });
const b = tabs.createTab('https://b.test/');
tabs.setLocked(crm, true);
const found = tabs.findTab((t) => t.appScope && t.appScope.appId === 'crm');
const none = tabs.findTab((t) => t.url === 'https://nope.test/');
const focused = tabs.focusTab(found.id);
process.stdout.write(JSON.stringify({ found: found && { id: found.id, locked: found.locked, app: found.appScope.appId, keys: Object.keys(found).sort() }, none, focused, active: tabs.activeId, count: tabs.list().length }));
""")
        self.assertEqual(out["found"]["app"], "crm")
        self.assertTrue(out["found"]["locked"])
        self.assertEqual(out["found"]["keys"], ["appScope", "id", "locked", "pinned", "url"])
        self.assertIsNone(out["none"])
        self.assertEqual(out["focused"], out["found"]["id"])
        self.assertEqual(out["active"], out["found"]["id"], "a locked tab is still focused: it is the person's own switch")
        self.assertEqual(out["count"], 3)

    @pending("M10-C4")
    def test_external_links_open_a_new_ordinary_tab_and_in_app_navigation_is_allowed(self):
        out = self._run("""
const tabs = new TabManager(win, { getContentBounds: bounds, pwqPath: '/x/pwq.html' });
const opened = [];
tabs.onExternalLink = (url) => { opened.push(url); return tabs.createTab(url); };
const app = tabs.createTab('file:///x/mapstation/index.html', { preload: '/p.js', restrictNavigation: true, appId: 'mapstation', consumerId: 'mapstation-ui' });
const wc = tabs.tabs.get(app).view.webContents;
const nav = (url) => { const e = { prevented: false, preventDefault() { this.prevented = true; } }; wc.handlers['will-navigate'].forEach((h) => h(e, url)); return e.prevented; };
const r = {};
r.external = nav('https://www.openstreetmap.org/copyright');
r.inApp = nav('file:///x/mapstation/p1.txt');
r.otherFile = nav('file:///etc/passwd');
r.self = nav('file:///x/mapstation/index.html');
r.open = wc.openHandler({ url: 'https://example.org/' }).action;
r.openFile = wc.openHandler({ url: 'file:///x/other.html' }).action;
r.opened = opened; r.count = tabs.list().length; r.appStillActiveUrl = tabs.tabs.get(app).url;
process.stdout.write(JSON.stringify(r));
""")
        self.assertTrue(out["external"], "the app tab itself never navigates to the external site")
        self.assertFalse(out["inApp"], "navigation inside the app's own directory is allowed")
        self.assertTrue(out["otherFile"])
        self.assertFalse(out["self"])
        self.assertEqual(out["open"], "deny")
        self.assertEqual(out["openFile"], "deny")
        self.assertEqual(out["opened"], ["https://www.openstreetmap.org/copyright", "https://example.org/"])
        self.assertEqual(out["count"], 3, "two new ordinary tabs were opened for the two http(s) links")

    @pending("M10-C3")
    def test_main_opens_plain_apps_as_app_tabs_and_restores_their_scope(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        open_fn = main[main.index("async function openRegisteredApp"):][:3000]
        self.assertIn("plain", open_fn)
        self.assertIn("appTabOptions(", open_fn)
        reg = main[main.index("function registeredAppForUrl"):][:1500]
        self.assertIn("plain", reg.lower(), "session restore re-scopes plain app tabs")
        for handler in ("dashboards:open", "pwq:open", "crm:open"):
            body = main[main.index("ipcMain.handle('%s'" % handler):][:900]
            self.assertIn("findTab(", body, handler + " focuses an open tab first")
        self.assertIn("onExternalLink", main)


class AppsToolTests(unittest.TestCase):
    """M10-C6"""

    @pending("M10-C6")
    def test_apps_tool_lists_real_urls(self):
        r = m10_root("m10appstool")
        self.addCleanup(r.close)
        r.start()
        write_soul_settings(r.root, "berton", {"brief": True})
        self.assertEqual(r.text("apps"), "ALLY: none")
        make_app_dir(r.root, "mapstation")
        make_app_dir(r.root, "nodequest")
        r.text("brief", app="nodequest", for_whom="a learner", flourishing="curious")
        out = r.text("apps")
        lines = out.splitlines()
        self.assertEqual(lines[0], "mapstation (plain) file://%s/mapstation/index.html" % Path(r.root).resolve())
        self.assertEqual(lines[1], "nodequest (plain) file://%s/nodequest/index.html — for a learner" % Path(r.root).resolve())


if __name__ == "__main__":
    unittest.main()
