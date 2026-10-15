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
import sys
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
        # agent-authored pages and the outputs history refers to come back too
        self.assertEqual(self.content(".runtime/pages"), "ORIGINAL .runtime/pages\n")
        self.assertEqual(self.content(".runtime/tool_results"), "ORIGINAL .runtime/tool_results\n")

    def test_everything_reset_destroys_comes_back_from_the_prereset_backup_except_caches(self):
        self.populate()
        self.run_js("const r = await api.resetState(); await api.restoreFromZipPath(r.backup); return null;")
        for entry in self.manifest["entries"]:
            if not entry["reset"] or entry["role"] == "secret":
                continue
            if entry["role"] == "cache" and entry["path"] != ".runtime/tool_results":
                continue
            self.assertEqual(self.content(entry["path"]), "ORIGINAL %s\n" % entry["path"],
                             "Reset destroyed %s and the backup could not bring it back" % entry["path"])

    def test_restore_returns_to_the_saved_state_without_mixing_in_the_current_session(self):
        self.populate()
        result = self.run_js("""
            const r = await api.resetState();
            const fs = require('fs'), path = require('path');
            // the new session after Reset writes its own state
            fs.mkdirSync(path.join(api.ITER_DIR, '.runtime/das_projection'), { recursive: true });
            fs.writeFileSync(path.join(api.ITER_DIR, '.runtime/das_projection/item.txt'), 'NEW SESSION\\n');
            fs.writeFileSync(path.join(api.ITER_DIR, '.budget_exceeded'), 'NEW SESSION\\n');
            return await api.restoreFromZipPath(r.backup);
        """)
        self.assertNotEqual(self.content(".budget_exceeded"), "NEW SESSION\n")
        self.assertEqual(self.content(".runtime/das_projection"), "ORIGINAL .runtime/das_projection\n")
        self.assertIn(".budget_exceeded", result["cleared"])

    def test_import_merges_apps_so_an_archive_cannot_delete_shipped_app_code(self):
        self.populate()
        shipped = self.iter_dir / "apps" / "music" / "index.html"
        shipped.parent.mkdir(parents=True)
        shipped.write_text("SHIPPED MUSIC APP\n")
        donor = self.work / "donor.zip"
        with zipfile.ZipFile(donor, "w") as archive:
            archive.writestr("state_manifest.json", "{}")
            archive.writestr("apps/myapp/index.html", "DONOR APP\n")
        self.run_js("await api.restoreFromZipPath(%s); return null;" % json.dumps(str(donor)))
        self.assertEqual(shipped.read_text(), "SHIPPED MUSIC APP\n")
        self.assertEqual((self.iter_dir / "apps" / "myapp" / "index.html").read_text(), "DONOR APP\n")

    def test_service_that_will_not_stop_cancels_reset_reports_why_and_recovers(self):
        self.populate()
        result = self.run_js("""
            api.__override('stopMettaServer', async () => { throw new Error('did not stop cleanly'); });
            try { await api.resetState(); return { ran: true }; }
            catch (e) { return { message: e.message, busy: api.__busy(), calls: api.__calls.map((c) => c[0] + (c[1] && c[1].length ? ':' + c[1] : '')) }; }
        """)
        self.assertIn("nothing was deleted", result["message"])
        self.assertIn("would not stop", result["message"])
        self.assertIn("backup saved", result["message"])
        self.assertFalse(result["busy"])
        self.assertIn("atomspace:resume", result["calls"])
        for entry in self.manifest["entries"]:
            self.assertIsNotNone(self.content(entry["path"]), "deleted %s although reset was cancelled" % entry["path"])

    def test_three_prereset_backups_are_kept(self):
        self.populate()
        self.run_js("""
            for (let i = 0; i < 5; i++) { await api.writeStateArchive('prereset-'); await new Promise((r) => setTimeout(r, 5)); }
            return null;
        """)
        files = [p.name for p in (self.user_data / "auto_backups").iterdir()]
        self.assertEqual(sum(f.startswith("prereset-") for f in files), 3)

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



@unittest.skipUnless(NODE, "needs node")
class SuperviseIterRevisionLogTests(unittest.TestCase):
    """R3: auto-resuming a desired-running Iter at app launch is not a crash recovery."""

    setUp = MainJsStateLifecycleTests.setUp
    tearDown = MainJsStateLifecycleTests.tearDown
    run_js = MainJsStateLifecycleTests.run_js

    SCENARIO = """
        const started = [];
        api.__override('runHotloadControl', async () => ({ action: 'none', active: { status: 'stable' } }));
        api.__override('startIterWithAtomspace', async () => { started.push('start'); return { started: true }; });
        api.__eval('iterDesiredRunning = true');
        api.__eval('iterProcess = null');
        %s
        await api.__eval('superviseIterRevision')();
        return { started, logs: api.__calls.filter((c) => c[0] === 'log').map((c) => c[1]) };
    """

    def test_launch_resume_is_not_reported_as_a_crash(self):
        result = self.run_js(self.SCENARIO % "")
        self.assertEqual(result["started"], ["start"])
        self.assertIn("[iter] resuming (was running when the app last closed)", result["logs"])
        self.assertFalse(any("exited unexpectedly" in line for line in result["logs"]), result["logs"])

    def test_exit_after_a_start_in_this_session_is_a_recovery(self):
        result = self.run_js(self.SCENARIO % "api.__eval('iterStartedThisSession = true');")
        self.assertEqual(result["started"], ["start"])
        self.assertIn("[recovery] Iter exited unexpectedly; restarting last-known-good generation", result["logs"])

    def test_spawning_iter_marks_it_started_this_session(self):
        source = (ROOT / "main.js").read_text()
        spawn_at = source.index("iterProcess = spawn(")
        self.assertIn("iterStartedThisSession = true", source[spawn_at:spawn_at + 300])


@unittest.skipUnless(NODE, "needs node")
class AtomspaceServiceCodeUpgradeTests(unittest.TestCase):
    """The AtomSpace service outlives the app; a code update must restart it (before Iter starts),
    otherwise new service code (e.g. the Milestone 5 kb backfill) never runs until a reboot."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.work = Path(self.temporary.name)
        self.repo = self.work / "repo"
        self.repo.mkdir()
        shutil.copy2(ROOT / "main.js", self.repo / "main.js")
        shutil.copytree(ROOT / "bridge", self.repo / "bridge")
        self.iter_dir = self.repo / "iter"
        shutil.copytree(ROOT / "iter" / "iterbrow_runtime", self.iter_dir / "iterbrow_runtime",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("metta_server.py", "metta_query_worker.py", "state_manifest.json"):
            shutil.copy2(ROOT / "iter" / name, self.iter_dir / name)
        self.user_data = self.work / "userData"
        self.user_data.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

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

    def python_hash(self):
        sys.path.insert(0, str(ROOT / "iter"))
        import metta_server
        return metta_server.service_code_hash(self.iter_dir)

    def test_node_and_python_fingerprints_agree_and_follow_the_code(self):
        node_hash = self.run_js("return api.__eval('serviceCodeHash()');")
        self.assertEqual(node_hash, self.python_hash())
        (self.iter_dir / "iterbrow_runtime" / "kb_terms.py").write_text("# changed\n")
        changed = self.run_js("return api.__eval('serviceCodeHash()');")
        self.assertNotEqual(changed, node_hash)
        self.assertEqual(changed, self.python_hash())

    SCENARIO = """
        const stopped = [];
        api.__override('retireOwnedLegacyMettaServer', async () => ({ already: true }));
        api.__override('stopMettaServer', async () => { stopped.push(true); return { stopped: true }; });
        api.__override('inspectAtomspaceLockOwner', async () => ({ status: 'error', error: 'TEST-SPAWN-POINT' }));
        const status = { ready: true, epoch: 'e1', commit: 7 };
        %s
        api.__override('callAtomspace', async (method) => {
          if (method === 'status' && !stopped.length) return status;
          throw new Error('no service');
        });
        const result = await api.__eval('startMettaServerOwned()');
        const logs = api.__calls.filter((c) => c[0] === 'log').map((c) => c[1]);
        return { result, stopped: stopped.length, logs };
    """

    def test_service_with_current_code_is_reused(self):
        out = self.run_js(self.SCENARIO % "status.code_hash = api.__eval('serviceCodeHash()');")
        self.assertTrue(out["result"].get("already"), out)
        self.assertEqual(out["stopped"], 0)

    def test_service_running_older_code_is_restarted_before_iter_starts(self):
        out = self.run_js(self.SCENARIO % "")  # a pre-fingerprint service reports no code_hash
        self.assertEqual(out["stopped"], 1, out)
        self.assertTrue(any("service code changed on disk" in line for line in out["logs"]), out["logs"])
        # It went on to the start path (stopped here by the test before anything is spawned).
        self.assertIn("lock owner cannot be verified", out["result"].get("error", ""), out)

    def test_service_is_not_restarted_under_a_running_iter(self):
        out = self.run_js(self.SCENARIO % "status.code_hash = 'old'; api.__eval('iterProcess = { pid: 1 }');")
        self.assertTrue(out["result"].get("already"), out)
        self.assertEqual(out["stopped"], 0)

    def test_failed_stop_keeps_the_running_service(self):
        out = self.run_js((self.SCENARIO % "status.code_hash = 'old';").replace(
            "async () => { stopped.push(true); return { stopped: true }; }",
            "async () => { throw new Error('did not stop cleanly'); }"))
        self.assertTrue(out["result"].get("already"), out)
        self.assertTrue(any("keeping the running one" in line for line in out["logs"]), out["logs"])


if __name__ == "__main__":
    unittest.main()
