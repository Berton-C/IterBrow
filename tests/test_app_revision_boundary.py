#!/usr/bin/env python3
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppRevisionBoundaryTests(unittest.TestCase):
    def test_existing_python_hotload_surface_is_unchanged(self):
        source = (
            ROOT / "iter" / "iterbrow_runtime" / "hotload_manager.py"
        ).read_text(encoding="utf-8")
        self.assertIn('MANAGED_ROOTS = ("tools", "transformations", "channels")', source)
        self.assertNotIn("app_revisions", source)

    def test_electron_recovers_app_pointer_before_restoring_tabs(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        recovery = source.index("recoverAppRevisionsBeforeTabs")
        restore = source.index("const savedSession = loadTabSession()")
        self.assertLess(recovery, restore)
        self.assertIn("runAppRevisionControl", source)
        self.assertIn("superviseAppRevision", source)
        self.assertIn("loadAppRevision", source)
        self.assertNotIn("const CRM_URL", source)

    def test_tab_manager_owns_revision_load_and_external_health_probe(self):
        source = (ROOT / "bridge" / "tab_manager.js").read_text(encoding="utf-8")
        self.assertIn("loadAppRevision", source)
        self.assertIn("did-finish-load", source)
        self.assertIn("did-fail-load", source)
        self.assertIn("window.iterApp.appContext", source)
        self.assertIn("dataset.iterReady", source)
        self.assertIn("allowedUrl", source)

    def test_iter_tool_cannot_report_health_or_promote_itself(self):
        source = (
            ROOT / "iter" / "tools" / "app_revision_control.py"
        ).read_text(encoding="utf-8")
        run_start = source.index("def run(")
        cli_start = source.index("def main(")
        agent_surface = source[run_start:cli_start]
        self.assertIn('action == "stage"', agent_surface)
        self.assertIn('action == "validate"', agent_surface)
        self.assertIn('action == "activate"', agent_surface)
        self.assertNotIn("supervisor_report", agent_surface)
        self.assertNotIn("promote", agent_surface)
        self.assertIn("--external-supervisor", source[cli_start:])

    def test_manifest_classifies_revision_state_and_control_suite_compiles_it(self):
        manifest = json.loads(
            (ROOT / "iter" / "state_manifest.json").read_text(encoding="utf-8")
        )
        entries = {entry["path"]: entry for entry in manifest["entries"]}
        revisions = entries[".runtime/app_revisions"]
        self.assertEqual(revisions["role"], "authoritative_state")
        self.assertEqual(revisions["owner"], "platform.app_revision")
        self.assertTrue(revisions["portable"])
        self.assertFalse(revisions["reset"])
        control = (ROOT / "scripts" / "test_control_plane.sh").read_text(encoding="utf-8")
        self.assertIn("iter/iterbrow_runtime/app_revision_manager.py", control)
        self.assertIn("iter/tools/app_revision_control.py", control)


if __name__ == "__main__":
    unittest.main()
