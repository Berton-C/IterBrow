#!/usr/bin/env python3
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_lifecycle():
    path = ROOT / "scripts" / "iterbrow_lifecycle.py"
    spec = importlib.util.spec_from_file_location("iterbrow_lifecycle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_dashboard_refresh():
    path = ROOT / "scripts" / "refresh_dashboard_projections.py"
    spec = importlib.util.spec_from_file_location("refresh_dashboard_projections", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerContractTests(unittest.TestCase):
    def test_standalone_entry_can_acquire_the_full_branch(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("ITERBROW_INSTALL_DIR", source)
        self.assertIn("ITERBROW_BRANCH", source)
        self.assertIn("TheWholeEnchilada", source)
        self.assertIn("exec /bin/bash", source)

    def test_explicit_lifecycle_commands_are_exposed(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        lifecycle = (ROOT / "scripts" / "iterbrow_lifecycle.sh").read_text(encoding="utf-8")
        for command in ("install", "update", "repair", "uninstall"):
            self.assertIn(command, source)
        self.assertIn("prepare-offline", lifecycle)
        self.assertIn("state_manifest.json", lifecycle)
        self.assertIn("ITERBROW_UPDATE_SOURCE", lifecycle)
        self.assertIn("rollback", lifecycle.lower())
        self.assertIn("validate-atomspace", lifecycle)
        self.assertIn('case "$LIFECYCLE_ROOT"', lifecycle)
        self.assertIn("refresh_dashboard_projections.py", lifecycle)
        self.assertLess(lifecycle.index("restore --root"), lifecycle.index("refresh_dashboard_projections.py"))

    def test_default_install_is_core_only_and_uses_lockfile(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("WITH_DEVELOPER_EXTRAS=0", source)
        self.assertIn("--developer-extras", source)
        self.assertIn("npm ci", source)
        self.assertNotIn("\nnpm install\n", source)

    def test_existing_user_nvm_is_loaded_before_homebrew_nvm(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        user_nvm = source.index('source "$NVM_DIR/nvm.sh"')
        homebrew_nvm = source.index('source "$(brew --prefix nvm)/nvm.sh"')
        self.assertLess(user_nvm, homebrew_nvm)

    def test_install_proves_native_recovery_before_launch(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        smoke = source.index("smoke_atomspace_service.py")
        restored_state = source.index("validate-atomspace")
        dashboards = source.index("refresh_dashboard_projections.py")
        readiness = source.index("iterbrow_readiness.py")
        launch = source.index("exec npm start")
        self.assertLess(smoke, restored_state)
        self.assertLess(restored_state, readiness)
        self.assertLess(restored_state, dashboards)
        self.assertLess(dashboards, readiness)
        self.assertIn("--initialize-if-missing", source)
        self.assertLess(smoke, readiness)
        self.assertLess(readiness, launch)
        self.assertIn("--require installed", source)
        self.assertNotIn("installed and runtime-verified", source)

    def test_provider_secret_stays_in_private_app_onboarding(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("read -s", source)
        self.assertNotIn("OPENROUTER_API_KEY=", source)
        self.assertIn("Settings drawer", source)

    def test_native_hyperon_repair_detects_the_real_macos_failure_safely(self):
        probe = (ROOT / "scripts" / "native_engine.py").read_text(encoding="utf-8")
        repair = (ROOT / "scripts" / "install_native_hyperon.sh").read_text(encoding="utf-8")
        patch = (ROOT / "scripts" / "patches" / "hyperon-0.2.10-trie-key.patch").read_text(encoding="utf-8")

        self.assertIn("KNOWN_BROKEN_MACOS_BINARIES", probe)
        self.assertIn("--safe-preflight", repair)
        self.assertLess(repair.index("--safe-preflight"), repair.index("native_engine.py\"; then"))
        self.assertIn("range(2500)", probe)
        self.assertIn("engine.space().get_atoms()", probe)
        self.assertIn("(self.0 & TK_VALUE_MASK) - TK_MAX_EXPRESSION_SIZE", patch)
        self.assertIn('export CARGO_HOME="$NATIVE_BUILD/cargo-home"', repair)
        self.assertIn('export CC="$(xcrun --find clang)"', repair)
        self.assertIn('export SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"', repair)
        self.assertIn('-isysroot "$SDKROOT"', repair)
        self.assertIn("unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH", repair)
        self.assertIn('"$CXX" -O2 -shared', repair)
        self.assertIn("ITERBROW_NATIVE_BUILD_DIR", repair)
        self.assertIn("Retry without recompiling", repair)
        self.assertIn("NATIVE_SOURCE_COMMIT", repair)

    def test_lifecycle_snapshot_preserves_state_but_not_versioned_seeds(self):
        lifecycle = _load_lifecycle()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            current = base / "current"
            staged = base / "staged"
            archive = base / "state.tar.gz"
            manifest = {
                "schema_version": 1,
                "entries": [
                    {"path": "memory", "role": "authoritative_state"},
                    {"path": ".runtime/settings.json", "role": "secret"},
                    {"path": "seed.metta", "role": "source_seed"},
                ],
            }
            for root in (current, staged):
                (root / "iter").mkdir(parents=True)
                (root / "iter" / "state_manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
            (current / "iter" / "memory").mkdir()
            (current / "iter" / "memory" / "fact.txt").write_text("remember", encoding="utf-8")
            (current / "iter" / ".runtime").mkdir()
            (current / "iter" / ".runtime" / "settings.json").write_text("secret", encoding="utf-8")
            (current / "iter" / "seed.metta").write_text("old", encoding="utf-8")
            (staged / "iter" / "seed.metta").write_text("new", encoding="utf-8")

            lifecycle.snapshot(current, archive)
            lifecycle.restore(staged, archive)

            self.assertEqual((staged / "iter" / "memory" / "fact.txt").read_text(), "remember")
            self.assertEqual((staged / "iter" / ".runtime" / "settings.json").read_text(), "secret")
            self.assertEqual((staged / "iter" / "seed.metta").read_text(), "new")
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_dashboard_projection_refresh_requires_and_embeds_current_graph(self):
        refresh = _load_dashboard_refresh()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transforms = root / "iter" / "transformations"
            runtime = transforms / ".runtime"
            vendor = root / "iter" / "vendor"
            runtime.mkdir(parents=True)
            vendor.mkdir(parents=True)
            for filename in ("dashboard_atomspace.py", "dashboard_gallery.py"):
                shutil.copy2(ROOT / "iter" / "transformations" / filename, transforms / filename)
            shutil.copy2(ROOT / "iter" / "vendor" / "force-graph.js", vendor / "force-graph.js")
            (runtime / "space.metta").write_text(
                "(-- > placeholder ignored)\n(-- shared-one shared-two)\n",
                encoding="utf-8",
            )
            (root / "iter" / "dashboard_runtime.html").write_text("runtime", encoding="utf-8")
            (root / "iter" / "dashboard_context.html").write_text("context", encoding="utf-8")

            result = refresh.refresh(root)

            atomspace = (root / "iter" / "dashboard_atomspace.html").read_text(encoding="utf-8")
            gallery = (root / "iter" / "dashboard_gallery.html").read_text(encoding="utf-8")
            self.assertIn("window._spaceVizGraph=graph", atomspace)
            self.assertIn("force-graph.js", atomspace)
            self.assertIn("_spaceVizGraph", gallery)
            self.assertGreater(result["gallery_bytes"], result["atomspace_bytes"])


if __name__ == "__main__":
    unittest.main()
