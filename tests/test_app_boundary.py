#!/usr/bin/env python3
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ApplicationBoundaryTests(unittest.TestCase):
    def test_main_uses_typed_app_service_and_has_no_crm_whole_file_writer(self):
        source = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("ipcMain.handle('app:context'", source)
        self.assertIn("ipcMain.handle('app:command'", source)
        self.assertIn("ipcMain.handle('app:changes'", source)
        self.assertIn("iterbrow_runtime/app_contract.py", source)
        self.assertNotIn("ipcMain.handle('crm:write'", source)
        self.assertNotIn("ipcMain.handle('crm:read'", source)

    def test_scoped_preload_exposes_only_contract_operations(self):
        source = (ROOT / "bridge" / "app_preload.js").read_text(encoding="utf-8")
        self.assertIn("appContext", source)
        self.assertIn("appCommand", source)
        self.assertIn("appChanges", source)
        self.assertIn("subscribe", source)
        for forbidden in ("crmWrite", "crmRead", "fsWrite", "terminalRun", "appId:"):
            self.assertNotIn(forbidden, source)
        crm = (ROOT / "bridge" / "crm_preload.js").read_text(encoding="utf-8")
        self.assertNotIn("crmWrite", crm)
        self.assertNotIn("crmRead", crm)

    def test_tab_scope_is_navigation_locked_and_bound_to_webcontents(self):
        source = (ROOT / "bridge" / "tab_manager.js").read_text(encoding="utf-8")
        self.assertIn("appId", source)
        self.assertIn("consumerId", source)
        self.assertIn("additionalArguments", source)
        self.assertIn("appScopeForWebContentsId", source)
        self.assertIn("restrictNavigation", source)
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("appScopeForWebContentsId", main)
        self.assertIn("event.sender.id", main)

    def test_crm_and_second_fixture_use_same_contract_without_file_names(self):
        crm = (ROOT / "iter" / "crm" / "index.html").read_text(encoding="utf-8")
        fixture = (
            ROOT / "tests" / "fixtures" / "app_contract_fixture.html"
        ).read_text(encoding="utf-8")
        for source in (crm, fixture):
            self.assertIn("iterApp", source)
            self.assertIn("appContext", source)
            self.assertIn("appCommand", source)
            self.assertNotIn("crmWrite", source)
            self.assertNotIn("contacts.json", source)
        self.assertIn("consumerId: 'crm-ui'", crm)
        self.assertIn("consumerId: 'contract-fixture'", fixture)

    def test_crm_visible_undo_uses_the_typed_contract(self):
        crm = (ROOT / "iter" / "crm" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="undo"', crm)
        self.assertIn("type:'undo'", crm)
        self.assertIn("target_command_id:target", crm)
        self.assertNotIn("D.contacts =", crm)

    def test_manifest_declares_seed_and_json_as_projection(self):
        manifest = json.loads(
            (ROOT / "iter" / "state_manifest.json").read_text(encoding="utf-8")
        )
        entries = {item["path"]: item for item in manifest["entries"]}
        seed = entries["seeds/application_contract.metta"]
        self.assertEqual(seed["role"], "source_seed")
        self.assertEqual(seed["owner"], "cognition.application_contract")
        crm = entries["crm/data"]
        self.assertEqual(crm["role"], "projection")
        self.assertEqual(crm["owner"], "application.crm_projection")


if __name__ == "__main__":
    unittest.main()
