#!/usr/bin/env python3
"""M6-B1..B3: Soul settings per person, the panel, and what reaches the prompt.

Spec: docs/milestones/M6_soul_base.md section B.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import pending, soul_settings, FEATURES, DEFAULT_ON, read_manifest, REPO, ITER_SRC  # noqa: E402


class SettingsFileTests(unittest.TestCase):
    """M6-B1"""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m6set-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))
        self.env = mock.patch.dict(os.environ, {"ITER_DIR": self.temp})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _write(self, payload):
        path = Path(self.temp) / ".runtime" / "soul_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        return path

    def test_missing_file_means_defaults_forks_and_brief_on_everything_else_off(self):
        s = soul_settings()
        settings = s.load()
        self.assertEqual(settings["schema_version"], 1)
        self.assertEqual(s.person(), "guest")
        for feature in FEATURES:
            self.assertEqual(s.enabled(feature), feature in DEFAULT_ON, feature)
        self.assertEqual(s.frequency(), "occasional")
        self.assertEqual(s.tone(), "warm")
        self.assertEqual(s.budget(), 1)
        self.assertFalse((Path(self.temp) / ".runtime" / "soul_settings.json").exists(), "reading never writes")

    def test_settings_are_scoped_to_the_current_person(self):
        self._write({"schema_version": 1, "person": "bright",
                     "people": {"bright": {"features": {"forks": False, "read": True}, "frequency": "whisper",
                                           "tone": "playful", "budget_per_cycle": 2},
                                "berton": {"features": {"wonder": True}}}})
        s = soul_settings()
        self.assertEqual(s.person(), "bright")
        self.assertFalse(s.enabled("forks"))
        self.assertTrue(s.enabled("read"))
        self.assertTrue(s.enabled("brief"), "unset features keep their defaults")
        self.assertEqual(s.frequency(), "whisper")
        self.assertEqual(s.tone(), "playful")
        self.assertEqual(s.budget(), 2)
        berton = s.for_person("berton")
        self.assertTrue(berton["features"]["wonder"])
        self.assertTrue(berton["features"]["forks"])
        self.assertEqual(berton["frequency"], "occasional")
        unknown = s.for_person("someone-new")
        self.assertEqual(unknown["features"]["forks"], True)
        self.assertEqual(unknown["features"]["read"], False)

    def test_corrupt_values_fall_back_without_raising(self):
        self._write({"schema_version": 1, "person": "berton",
                     "people": {"berton": {"features": "nope", "frequency": "loud", "tone": 7, "budget_per_cycle": -3}}})
        s = soul_settings()
        self.assertTrue(s.enabled("forks"))
        self.assertEqual(s.frequency(), "occasional")
        self.assertEqual(s.tone(), "warm")
        self.assertEqual(s.budget(), 1)
        (Path(self.temp) / ".runtime" / "soul_settings.json").write_text("{not json")
        self.assertEqual(soul_settings().person(), "guest")

    def test_manifest_declares_the_file_as_portable_application_state_not_reset(self):
        entries = {e["path"]: e for e in read_manifest()["entries"]}
        entry = entries.get(".runtime/soul_settings.json")
        self.assertIsNotNone(entry, "state_manifest.json must declare .runtime/soul_settings.json")
        self.assertEqual(entry["role"], "application_state")
        self.assertTrue(entry["portable"])
        self.assertFalse(entry["reset"], "a factory reset keeps the person's Soul tuning")


class PanelTests(unittest.TestCase):
    """M6-B2: the sidebar Soul panel and its own IPC."""

    def test_dock_panel_is_registered_after_settings(self):
        js = (REPO / "renderer" / "renderer.js").read_text(encoding="utf-8")
        html = (REPO / "renderer" / "index.html").read_text(encoding="utf-8")
        self.assertIn("'soul': {", js)
        order_line = js[js.index("const DOCK_DEFAULT_ORDER"):].splitlines()[0]
        self.assertIn("'soul'", order_line)
        self.assertLess(order_line.index("'settings'"), order_line.index("'soul'"))
        self.assertIn('id="soul"', html)
        self.assertIn('class="dock-panel"', html[html.index('id="soul"') - 200:html.index('id="soul"') + 50])
        for feature in FEATURES:
            self.assertIn('data-soul-feature="%s"' % feature, html, feature)
        for control in ("soul-person", "soul-frequency", "soul-tone", "soul-budget"):
            self.assertIn('id="%s"' % control, html, control)
        for person in ("berton", "bright", "haley", "guest"):
            self.assertIn('value="%s"' % person, html, person)

    def test_soul_settings_have_their_own_ipc_and_never_touch_model_keys(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        self.assertIn("ipcMain.handle('soul:load'", main)
        self.assertIn("ipcMain.handle('soul:save'", main)
        self.assertIn("soul_settings.json", main)
        self.assertIn("loadSoulSettings", preload)
        self.assertIn("saveSoulSettings", preload)
        save = main[main.index("ipcMain.handle('soul:save'"):][:1500]
        self.assertNotIn("apiKey", save)
        self.assertNotIn("saveSettings(", save, "Soul tuning is not merged into settings.json")
        self.assertIn("0o600", save)

    def test_person_selector_is_the_one_source_of_who_is_here(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        # Every choice IPC takes the person from the soul settings file, never from the renderer's claim.
        choice = main[main.index("ipcMain.handle('chat:choice'"):][:1200]
        self.assertIn("loadSoulSettings()", choice)
        self.assertNotIn("person)", choice.split("=>")[0], "the renderer does not pass a person")


class PromptTests(unittest.TestCase):
    """M6-B3: a feature that is off leaves no trace; on adds exactly one block."""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m6prompt-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))

    def _run_presence(self, settings):
        import subprocess
        runtime = Path(self.temp) / ".runtime"
        runtime.mkdir(exist_ok=True)
        (runtime / "soul_settings.json").write_text(json.dumps(settings))
        code = ("import sys, json, importlib.util; spec = importlib.util.spec_from_file_location('t', sys.argv[1]);"
                "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
                "msgs, _ = m.transform([{'role': 'system', 'content': 'base'}], []); print(json.dumps(msgs))")
        proc = subprocess.run([sys.executable, "-c", code, str(ITER_SRC / "transformations" / "soul_presence.py")],
                              cwd=self.temp, env=dict(os.environ, ITER_DIR=self.temp), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_all_features_off_adds_nothing(self):
        msgs = self._run_presence({"schema_version": 1, "person": "berton",
                                   "people": {"berton": {"features": {f: False for f in FEATURES}}}})
        self.assertEqual(msgs, [{"role": "system", "content": "base"}])

    def test_features_on_add_exactly_one_short_block_naming_the_person(self):
        msgs = self._run_presence({"schema_version": 1, "person": "bright",
                                   "people": {"bright": {"features": {"forks": True, "read": True}, "tone": "playful"}}})
        content = msgs[-1]["content"]
        self.assertEqual(content.count("## Soul ("), 1)
        self.assertIn("## Soul (bright)", content)
        self.assertIn("forks", content)
        self.assertIn("read", content)
        self.assertNotIn("wonder", content)
        self.assertIn("playful", content)
        self.assertIn("[choice", content, "the model is told how a person's answer comes back")
        self.assertLess(len(content) - len("base"), 900, "the presence block stays short")
        for stale in ("Core Values", "ALIVE", "SILENT", "compass_state", "clarity:", "stewardship:"):
            self.assertNotIn(stale, content, stale)


if __name__ == "__main__":
    unittest.main()
