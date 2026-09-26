#!/usr/bin/env python3
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MainAtomspaceUpgradeTests(unittest.TestCase):
    def test_single_instance_lock_precedes_window_creation(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        lock = source.index("app.requestSingleInstanceLock")
        ready = source.index("app.whenReady().then(createWindow)")
        self.assertLess(lock, ready)
        self.assertIn("if (hasSingleInstanceLock)", source)
        self.assertIn("app.on('second-instance'", source)

    def test_browser_bridge_endpoint_is_checkout_scoped(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn(
            "const ITER_BRIDGE_SOCKET = process.env.ITER_BRIDGE_SOCKET || "
            "`/tmp/iter-browser-${ITER_INSTANCE_ID}.sock`",
            source,
        )
        self.assertIn("ITER_BRIDGE_SOCKET,", source)
        self.assertIn(
            "startBridgeServer(tabs, pushLog, ITER_BRIDGE_SOCKET, {", source
        )
        start = source.index("async function startIter()")
        stop = source.index("function stopIter()", start)
        start_source = source[start:stop]
        self.assertIn("await browserBridgeReadyPromise", start_source)
        self.assertIn("bridge.status !== 'listening'", start_source)
        self.assertLess(
            start_source.index("await browserBridgeReadyPromise"),
            start_source.index("startIterProcess()"),
        )

    def test_legacy_endpoint_is_retired_only_after_checkout_identity_check(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("function callAtomspaceAt(socketPath", source)
        self.assertIn("async function retireOwnedLegacyMettaServer()", source)
        self.assertIn("status.state_dir", source)
        self.assertIn("status.iter_dir", source)
        start = source.index("async function startMettaServerOwned()")
        retire = source.index("await retireOwnedLegacyMettaServer();", start)
        inspect_current = source.index("let currentStatus = null;", start)
        self.assertLess(retire, inspect_current)
        self.assertIn("legacy socket belongs to another checkout; leaving it untouched", source)

    def test_detached_atomspace_receives_the_computed_browser_endpoint(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        start = source.index("async function startMettaServerOwned()")
        end = source.index("async function startMettaServer()", start)
        spawn = source[source.index("mettaProcess = spawn(", start):end]
        # The checkout-scoped endpoint is a main-process constant, not normally
        # in process.env when launched by npm start. Foundry runs inside this
        # detached service and must receive the same endpoint as Iter itself.
        self.assertRegex(spawn, r"env:\s*\{\s*\.\.\.process\.env,\s*ITER_METTA_SOCKET,\s*ITER_BRIDGE_SOCKET,\s*ITER_DIR,")
        self.assertIn("detached: true", spawn)

    def test_atomspace_endpoint_recovery_never_unlinks_an_unverified_owner(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("inspectSocketPath, startBridgeServer", source)
        self.assertIn("function inspectAtomspaceLockOwner()", source)
        self.assertIn("metta_server\\.py", source)
        self.assertIn("async function startMettaServerOwned()", source)
        self.assertIn("if (mettaStartPromise) return mettaStartPromise", source)

        start = source.index("async function startMettaServerOwned()")
        wrapper = source.index("async function startMettaServer()", start)
        owned = source[start:wrapper]
        probe = owned.index("await inspectSocketPath(ITER_METTA_SOCKET")
        stale = owned.index("if (endpoint.status === 'stale')")
        unlink = owned.index("fs.unlinkSync(ITER_METTA_SOCKET)", stale)
        self.assertLess(probe, stale)
        self.assertLess(stale, unlink)
        self.assertNotIn(
            "try { fs.unlinkSync(ITER_METTA_SOCKET); } catch (_) {}", owned
        )
        self.assertIn("owner.status === 'foreign-live'", owned)
        self.assertIn("owner.status === 'owned-live'", owned)
        self.assertIn("await waitForProcessExit(owner.pid)", owned)

    def test_iter_start_stop_intent_survives_app_restart(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("iterAutoStart: false", source)
        self.assertIn("function persistIterDesiredRunning(desired)", source)

        start = source.index("async function startIter()")
        stop = source.index("function stopIter()", start)
        wait = source.index("function stopIterAndWait", stop)
        self.assertIn("persistIterDesiredRunning(true)", source[start:stop])
        self.assertIn("persistIterDesiredRunning(false)", source[stop:wait])

        window = source.index("function createWindow()")
        restore = source.index(
            "iterDesiredRunning = initialSettings.iterAutoStart === true", window
        )
        automatic = source.index("if (iterDesiredRunning)", restore)
        self.assertLess(restore, automatic)
        self.assertIn("startIterWithAtomspace()", source[automatic:automatic + 500])

    def test_packaged_app_bootstraps_a_separate_writable_workspace(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("const BUNDLED_ITER_DIR = path.join(__dirname, 'iter')", source)
        self.assertIn("app.isPackaged", source)
        self.assertIn("ITERBROW_WORKSPACE_DIR", source)
        self.assertIn("function bootstrapPackagedIterWorkspace()", source)
        self.assertIn("fs.cpSync(BUNDLED_ITER_DIR, temporary", source)
        self.assertIn("fs.renameSync(temporary, ITER_DIR)", source)
        bootstrap = source.index("bootstrapPackagedIterWorkspace();")
        manifest = source.index("const STATE_MANIFEST_PATH")
        self.assertLess(bootstrap, manifest)

    def test_package_is_an_allowlisted_template_not_live_state(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        files = package["build"]["files"]
        self.assertNotIn("iter/**/*", files)
        for required in (
            "iter/iter.py",
            "iter/metta_server.py",
            "iter/iterbrow_runtime/**/*",
            "iter/tools/**/*",
            "iter/transformations/**/*",
            "iter/channels/**/*",
            "iter/seeds/**/*",
            "iter/vendor/**/*",
            "iter/apps/music/**/*",
            "iter/crm/**/*",
            "iter/pwq.html",
            "iter/pwq_seed.json",
            "iter/state_manifest.json",
        ):
            self.assertIn(required, files)
        for forbidden in (
            "iter/.runtime/**/*",
            "iter/private/**/*",
            "iter/memory/**/*",
            "iter/chroma_db/**/*",
            "iter/experience.json",
        ):
            self.assertNotIn(forbidden, files)

    def test_fresh_package_has_a_non_generated_dashboard_fallback(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("fs.existsSync(generated)", source)
        self.assertIn("renderer', 'dashboard_empty.html", source)
        self.assertTrue((ROOT / "renderer" / "dashboard_empty.html").is_file())


if __name__ == "__main__":
    unittest.main()
