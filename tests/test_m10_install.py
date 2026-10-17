#!/usr/bin/env python3
"""M10-B1..B3: installing the SDK into an app — the tool, NodeQuest first, the docs.

Spec: docs/milestones/M10_ally_sdk.md section B.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m10_support import (pending, m10_root, require_m10, write_soul_settings, make_app_dir, copy_nodequest, dir_digest, root_digest_excluding,  # noqa: E402
                         kernel_json, SDK, KERNEL_JSON, playwright_available, run_playwright, NODE, REPO, ITER_SRC)
from test_m7_brief import make_project  # noqa: E402


class InstallToolTests(unittest.TestCase):
    """M10-B1"""

    def setUp(self):
        self.r = m10_root("m10install")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_plain_app_gets_the_files_and_the_include_once(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        app = make_app_dir(self.r.root, "crm", body="<h1 id='title'>crm</h1>\n<script>window.crm = 1;</script>\n")
        self.assertTrue(self.r.text("ally_sdk", app="crm").startswith("ERROR: give crm a brief first"))
        self.r.text("brief", app="crm", for_whom="Berton, keeping track of people", flourishing="he reaches out")
        before_html = (app / "index.html").read_text()
        outside_before = root_digest_excluding(self.r.root, "crm")
        self.assertEqual(self.r.text("ally_sdk", app="crm"), "ALLY-SDK: installed in crm")
        self.assertEqual(root_digest_excluding(self.r.root, "crm"), outside_before, "nothing outside the app changed")
        self.assertEqual((app / "iter_ally.js").read_bytes(), SDK.read_bytes())
        self.assertEqual((app / "soul_kernel.json").read_bytes(), KERNEL_JSON.read_bytes())
        html = (app / "index.html").read_text()
        self.assertTrue(html.startswith(before_html.rstrip("\n").rsplit("</body>", 1)[0]) if "</body>" in before_html else html.startswith(before_html), "the page above the injection is unchanged")
        self.assertIn('<script src="iter_ally.js"></script>', html)
        self.assertIn('IterAlly.install({ brief: {for: "Berton, keeping track of people", flourishing: "he reaches out"}, person: "guest" })', html)
        digest = dir_digest(app)
        self.assertEqual(self.r.text("ally_sdk", app="crm"), "ALLY-SDK: already installed in crm")
        self.assertEqual(dir_digest(app), digest, "a second run changes nothing")
        self.assertTrue(self.r.text("ally_sdk", app="nope").startswith("ERROR: no app named"))

    def test_foundry_project_install_is_a_checkpointed_source_write(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        make_project(self.r.root, "orbit")
        src = Path(self.r.root) / "apps" / "orbit" / "src"
        (src / "index.html").write_text("<!doctype html><title>orbit</title><body><h1>Orbit</h1></body>")
        self.r.text("brief", app="orbit", for_whom="Bright", flourishing="lighter")
        history_before = len(list((Path(self.r.root) / "apps" / "orbit" / "history").glob("*.json")))
        self.assertEqual(self.r.text("ally_sdk", app="orbit"), "ALLY-SDK: installed in orbit")
        self.assertEqual((src / "iter_ally.js").read_bytes(), SDK.read_bytes())
        self.assertTrue((src / "soul_kernel.json").exists())
        html = (src / "index.html").read_text()
        self.assertIn('<script src="iter_ally.js"></script>', html)
        self.assertIn('brief: {for: "Bright", flourishing: "lighter"}', html)
        history = sorted((Path(self.r.root) / "apps" / "orbit" / "history").glob("*.json"), key=lambda p: p.stat().st_mtime)
        self.assertEqual(len(history), history_before + 1, "one checkpoint")
        record = json.loads(history[-1].read_text())
        self.assertEqual(record["provenance"], {"tool": "ally_sdk", "person": "berton"})
        self.assertEqual(self.r.text("ally_sdk", app="orbit"), "ALLY-SDK: already installed in orbit")


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class NodeQuestTests(unittest.TestCase):
    """M10-B2"""

    def test_nodequest_inherits_the_ally(self):
        r = m10_root("m10nodequest")
        self.addCleanup(r.close)
        r.start()
        write_soul_settings(r.root, "berton", {"brief": True})
        app = copy_nodequest(r.root)
        original = (app / "index.html").read_text(encoding="utf-8")
        r.text("brief", app="nodequest", for_whom="a learner who wants to understand, not pass", flourishing="they leave with a question they like")
        self.assertEqual(r.text("ally_sdk", app="nodequest"), "ALLY-SDK: installed in nodequest")
        html = (app / "index.html").read_text(encoding="utf-8")
        head_before = original.rsplit("</body>", 1)[0] if "</body>" in original else original
        self.assertTrue(html.startswith(head_before), "NodeQuest's own markup above the injection is byte-identical")
        out = json.loads(run_playwright("""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1000, "height": 700})
    pg.add_init_script("window.__fetches = []; window.fetch = (...a) => { window.__fetches.push(a); return Promise.reject(new Error('no network')); };")
    pg.goto(%s); pg.wait_for_timeout(800)
    print(json.dumps(pg.evaluate(\"\"\"(async () => {
  for (let i = 0; i < 50 && !(window.IterAlly && (() => { try { IterAlly.patterns(); return true; } catch (e) { return false; } })()); i++) await new Promise((r) => setTimeout(r, 100));
  const p = IterAlly.fork({ title: 'Which first?', a: { label: 'Wander', pattern: 'WonderPreservation' }, b: { label: 'Make it clear', pattern: 'SharedUnderstanding' }, topic: 'first-node' });
  await new Promise((r) => setTimeout(r, 50));
  document.querySelector('button.iter-ally-choice[data-choice="a"]').click();
  const pick = await p;
  return { brief: IterAlly.brief(), patterns: IterAlly.patterns().length, pick, cal: IterAlly.calibration().map((c) => [c.topic, c.pick]),
           fetches: window.__fetches.filter((f) => !String(f[0]).endsWith('soul_kernel.json')).length, title: document.title };
})()\"\"\"))); b.close()
""" % json.dumps("file://" + str(app / "index.html"))).strip().splitlines()[-1])
        self.assertEqual(out["brief"]["for"], "a learner who wants to understand, not pass")
        self.assertEqual(out["patterns"], 9)
        self.assertEqual(out["pick"], "a")
        self.assertEqual(out["cal"], [["first-node", "a"]])
        self.assertEqual(out["fetches"], 0, "no request other than the kernel file next to the SDK")


class DocsTests(unittest.TestCase):
    """M10-B3"""

    def test_agents_md_names_the_sdk_and_its_guarantees(self):
        require_m10()
        text = (ITER_SRC / "AGENTS.md").read_text(encoding="utf-8")
        start = text.index("## Soul")
        section = text[start:text.find("\n## ", start + 1)]
        for needle in ("ally_sdk", "iter_ally.js", "no gate", "never phones home", "brief is the app's Soul"):
            self.assertIn(needle, section, needle)
        self.assertIn("| `ally_sdk` |", text)
        self.assertIn("| `apps` |", text)
        self.assertLess(len(section), 6000)


if __name__ == "__main__":
    unittest.main()
