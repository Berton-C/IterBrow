#!/usr/bin/env python3
"""Milestone 2: Reset / Export / Import, driven through the real main.js.

Each test copies main.js, bridge/ and the iter/ manifest into a throwaway
checkout, fills ITER_DIR with a file for every manifest path, and runs a
small JS scenario against the real state functions (Electron and process
lifecycle stubbed)."""
import json
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "node" / "mainjs_harness.js"
NODE = shutil.which("node")


@unittest.skipUnless(NODE and shutil.which("zip") and shutil.which("unzip"), "needs node, zip and unzip")
class MainJsStateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.work = Path(self.temporary.name)
        self.repo = self.work / "repo"
        self.repo.mkdir()
        shutil.copy2(ROOT / "main.js", self.repo / "main.js")
        shutil.copytree(ROOT / "bridge", self.repo / "bridge")
        (self.repo / "iter" / "iterbrow_runtime").mkdir(parents=True)
        shutil.copy2(ROOT / "iter" / "iterbrow_runtime" / "openai_models.json",
                     self.repo / "iter" / "iterbrow_runtime" / "openai_models.json")
        shutil.copy2(ROOT / "iter" / "state_manifest.json", self.repo / "iter" / "state_manifest.json")
        self.iter_dir = self.repo / "iter"
        self.user_data = self.work / "userData"
        self.user_data.mkdir()
        self.manifest = json.loads((self.iter_dir / "state_manifest.json").read_text())
        # code that must survive everything
        (self.iter_dir / "tools").mkdir()
        (self.iter_dir / "tools" / "sample.py").write_text("def run():\n    return 1\n")

    def tearDown(self):
        self.temporary.cleanup()

    # -- helpers -----------------------------------------------------------
    def populate(self, marker="ORIGINAL"):
        """Create one file for every manifest path (a file inside directory-like paths)."""
        for entry in self.manifest["entries"]:
            target = self.iter_dir / entry["path"]
            if target.suffix:  # file-like path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("%s %s\n" % (marker, entry["path"]))
            else:
                target.mkdir(parents=True, exist_ok=True)
                (target / "item.txt").write_text("%s %s\n" % (marker, entry["path"]))

    def content(self, rel):
        target = self.iter_dir / rel
        if target.is_dir():
            target = target / "item.txt"
        return target.read_text() if target.exists() else None

    def run_js(self, body):
        scenario = self.work / "scenario.js"
        scenario.write_text("module.exports = async (api) => {\n" + textwrap.dedent(body) + "\n};\n")
        proc = subprocess.run([NODE, str(HARNESS), str(self.repo), str(self.user_data), str(scenario)],
                              capture_output=True, text=True, timeout=120)
        line = [l for l in proc.stdout.splitlines() if l.startswith("{")]
        self.assertTrue(line, "harness produced no result:\n" + proc.stdout + proc.stderr)
        reply = json.loads(line[-1])
        self.assertTrue(reply["ok"], reply.get("error"))
        return reply["result"]

    # -- tests ---------------------------------------------------------------
    def test_reset_clears_exactly_the_reset_paths_and_saves_a_backup_first(self):
        self.populate()
        result = self.run_js("""
            const r = await api.resetState();
            return { r, calls: api.__calls.map((c) => c[0]) };
        """)
        for entry in self.manifest["entries"]:
            present = self.content(entry["path"]) is not None
            if entry["reset"]:
                self.assertFalse(present, "reset left %s behind" % entry["path"])
            else:
                self.assertTrue(present, "reset deleted %s" % entry["path"])
        self.assertTrue((self.iter_dir / "tools" / "sample.py").exists(), "reset touched code")
        backup = Path(result["r"]["backup"])
        self.assertTrue(backup.exists() and backup.name.startswith("prereset-"))
        names = set(zipfile.ZipFile(backup).namelist())
        self.assertIn("memory/item.txt", names)
        self.assertIn("experience.json", names)
        calls = result["calls"]
        # the archive is written while the AtomSpace is still up, checkpointed first
        self.assertLess(calls.index("atomspace"), calls.index("stopMetta"))

    def test_pwq_board_is_cleared_by_factory_reset(self):
        self.populate()
        self.run_js("await api.resetState(); return null;")
        self.assertIsNone(self.content(".runtime/pwq"))
        self.assertIsNone(self.content(".runtime/pwq.json"))

    def test_reset_is_cancelled_and_nothing_deleted_when_backup_fails(self):
        self.populate()
        self.run_js("""
            api.__setWriteStateArchive(async () => { throw new Error('disk full'); });
            try { await api.resetState(); return 'reset ran'; }
            catch (e) { if (!/Reset cancelled/.test(e.message)) throw e; return 'cancelled'; }
        """)
        for entry in self.manifest["entries"]:
            self.assertIsNotNone(self.content(entry["path"]), "deleted %s without a backup" % entry["path"])

    def test_reset_then_restore_of_the_prereset_backup_returns_the_memory(self):
        self.populate()
        result = self.run_js("""
            const r = await api.resetState();
            await api.restoreFromZipPath(r.backup);
            return r.backup;
        """)
        self.assertEqual(self.content("memory"), "ORIGINAL memory\n")
        self.assertEqual(self.content("experience.json"), "ORIGINAL experience.json\n")
        self.assertEqual(self.content(".runtime/atomspace"), "ORIGINAL .runtime/atomspace\n")

    def test_prereset_backups_survive_the_rolling_autobackup_rotation(self):
        self.populate()
        self.run_js("""
            await api.resetState();
            for (let i = 0; i < 6; i++) {
              await api.writeStateArchive('autobackup-');
              await new Promise((r) => setTimeout(r, 5));
            }
            return null;
        """)
        files = sorted(p.name for p in (self.user_data / "auto_backups").iterdir())
        self.assertEqual(sum(f.startswith("prereset-") for f in files), 1)
        self.assertEqual(sum(f.startswith("autobackup-") for f in files), 4)

    def test_import_never_replaces_running_code_generations(self):
        self.populate()
        donor = self.work / "donor.zip"
        with zipfile.ZipFile(donor, "w") as archive:
            archive.writestr("state_manifest.json", "{}")
            archive.writestr("memory/item.txt", "DONOR memory\n")
            archive.writestr(".runtime/hotload/item.txt", "DONOR CODE\n")
        self.run_js("await api.restoreFromZipPath(%s); return null;" % json.dumps(str(donor)))
        self.assertEqual(self.content("memory"), "DONOR memory\n")
        self.assertEqual(self.content(".runtime/hotload"), "ORIGINAL .runtime/hotload\n")


if __name__ == "__main__":
    unittest.main()
