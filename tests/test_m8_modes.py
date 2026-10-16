#!/usr/bin/env python3
"""M8-A1..A4: modes — the setting, the tool, the block per mode, and the new default.

Spec: docs/milestones/M8_soul_presence.md section A.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m8_support import (pending, m8_root, require_m8, soul_settings, write_soul_settings, run_transformation,  # noqa: E402
                        tool_entry, MODES, FEATURES, REPO, ITER_SRC)


class ModeSettingTests(unittest.TestCase):
    """M8-A1"""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m8mode-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))
        env = mock.patch.dict(os.environ, {"ITER_DIR": self.temp})
        env.start()
        self.addCleanup(env.stop)

    def test_mode_defaults_to_open_and_invalid_falls_back(self):
        require_m8()
        s = soul_settings()
        self.assertEqual(s.MODES, tuple(MODES))
        self.assertEqual(s.mode(), "open")
        write_soul_settings(self.temp, "berton", {"forks": True}, mode="loud")
        self.assertEqual(soul_settings().mode(), "open")
        write_soul_settings(self.temp, "berton", {"forks": True}, mode="jam")
        self.assertEqual(soul_settings().mode(), "jam")
        self.assertEqual(soul_settings().for_person("bright")["mode"], "open")

    def test_set_mode_writes_only_the_mode_atomically_and_private(self):
        require_m8()
        write_soul_settings(self.temp, "berton", {"forks": False, "felt": True}, tone="playful", budget_per_cycle=3)
        s = soul_settings()
        s.set_mode("berton", "critique")
        path = Path(self.temp) / ".runtime" / "soul_settings.json"
        saved = json.loads(path.read_text())
        self.assertEqual(saved["people"]["berton"]["mode"], "critique")
        self.assertEqual(saved["people"]["berton"]["features"], {"forks": False, "felt": True}, "features untouched")
        self.assertEqual(saved["people"]["berton"]["tone"], "playful")
        self.assertEqual(saved["people"]["berton"]["budget_per_cycle"], 3)
        self.assertEqual(saved["person"], "berton")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse(list(path.parent.glob("*.tmp")), "no temp file left behind")
        with self.assertRaises(ValueError):
            s.set_mode("berton", "loud")
        self.assertEqual(soul_settings().mode(), "critique")
        # A person with no profile yet gets one holding just the mode.
        s.set_mode("haley", "jam")
        self.assertEqual(json.loads(path.read_text())["people"]["haley"], {"mode": "jam"})

    def test_panel_and_main_js_carry_the_mode(self):
        html = (REPO / "renderer" / "index.html").read_text(encoding="utf-8")
        main = (REPO / "main.js").read_text(encoding="utf-8")
        js = (REPO / "renderer" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn('id="soul-mode"', html)
        for mode in MODES:
            self.assertIn('value="%s"' % mode, html[html.index('id="soul-mode"'):][:800], mode)
        clean = main[main.index("function cleanSoulSettings"):][:2500]
        for mode in MODES:
            self.assertIn("'%s'" % mode, clean, mode)
        self.assertIn("soul-mode", js)


class ModeToolTests(unittest.TestCase):
    """M8-A2"""

    def setUp(self):
        self.r = m8_root("m8modetool")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_tool_switches_the_current_persons_mode(self):
        write_soul_settings(self.r.root, "bright", {"forks": True})
        self.assertEqual(self.r.text("soul_mode", mode="jam"), "MODE: jam (was open)")
        self.assertEqual(self.r.text("soul_mode", mode="museum"), "MODE: museum (was jam)")
        saved = json.loads((Path(self.r.root) / ".runtime" / "soul_settings.json").read_text())
        self.assertEqual(saved["people"]["bright"]["mode"], "museum")
        self.assertEqual(self.r.text("soul_mode", mode="loud"), "ERROR: mode must be one of open, jam, quiet, critique, museum")

    def test_presence_tells_iter_the_switch_words(self):
        write_soul_settings(self.r.root, "bright", {"forks": True})
        msgs, _ = run_transformation(self.r.root, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        content = msgs[-1]["content"]
        self.assertIn("soul_mode", content)
        for word in ("jam", "quiet", "critique", "museum night"):
            self.assertIn(word, content, word)


class ModeBlockTests(unittest.TestCase):
    """M8-A3"""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m8block-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))

    def _presence(self, mode, features=None, **profile):
        write_soul_settings(self.temp, "berton", features if features is not None else {"forks": True, "felt": True}, mode=mode, **profile)
        tools = [tool_entry("felt"), tool_entry("card"), tool_entry("shell")]
        return run_transformation(self.temp, "soul_presence.py", tools=tools, env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})

    def test_quiet_means_no_block_and_no_felt_tool(self):
        msgs, tools = self._presence("quiet", {f: True for f in FEATURES})
        self.assertEqual(msgs, [{"role": "system", "content": "base"}])
        self.assertEqual([t["function"]["name"] for t in tools], ["card", "shell"])

    def test_each_mode_has_its_line_and_open_has_none(self):
        expected = {
            "jam": "Mode: jam — riff freely; playful variant names; a fork may hold three poles; felt notes welcome.",
            "critique": "Mode: critique — walk the app as the person its brief names; report what is technically correct and dead with soul_absent_test; change nothing.",
            "museum": "Mode: museum night — walk kept and rejected variants with museum_night and say why, using what you've learned of their taste.",
        }
        for mode, line in expected.items():
            msgs, tools = self._presence(mode)
            content = msgs[-1]["content"]
            self.assertIn(line, content, mode)
            self.assertEqual(content.count("Mode:"), 1, mode)
            self.assertEqual([t["function"]["name"] for t in tools], ["felt", "card", "shell"], mode)
        msgs, _ = self._presence("open")
        self.assertNotIn("Mode:", msgs[-1]["content"])

    def test_cap_holds_with_every_feature_on_in_the_longest_mode(self):
        msgs, _ = self._presence("critique", {f: True for f in FEATURES}, budget_per_cycle=3, frequency="chatty")
        self.assertIn("Mode: critique", msgs[-1]["content"])
        self.assertLess(len(msgs[-1]["content"]) - len("base"), 900)


class DefaultTests(unittest.TestCase):
    """M8-A4: margin is on by default."""

    def test_margin_is_a_default_everywhere_the_defaults_are_stated(self):
        require_m8()
        temp = tempfile.mkdtemp(prefix="m8def-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        with mock.patch.dict(os.environ, {"ITER_DIR": temp}):
            s = soul_settings()
            self.assertTrue(s.enabled("margin"))
            self.assertTrue(s.enabled("forks"))
            self.assertTrue(s.enabled("brief"))
            self.assertFalse(s.enabled("felt"))
        js = (REPO / "renderer" / "renderer.js").read_text(encoding="utf-8")
        defaults = js[js.index("const SOUL_DEFAULTS"):][:400]
        self.assertIn("margin: true", defaults)
        import m6_support
        self.assertEqual(m6_support.DEFAULT_ON, {"forks", "brief", "margin"})


if __name__ == "__main__":
    unittest.main()
