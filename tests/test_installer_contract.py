#!/usr/bin/env python3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallerContractTests(unittest.TestCase):
    def test_standalone_entry_can_acquire_the_full_branch(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("ITERBROW_INSTALL_DIR", source)
        self.assertIn("ITERBROW_BRANCH", source)
        self.assertIn("TheWholeEnchilada", source)
        self.assertIn("exec /bin/bash", source)

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
        readiness = source.index("iterbrow_readiness.py")
        launch = source.index("exec npm start")
        self.assertLess(smoke, readiness)
        self.assertLess(readiness, launch)
        self.assertIn("--require installed", source)

    def test_provider_secret_stays_in_private_app_onboarding(self):
        source = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("read -s", source)
        self.assertNotIn("OPENROUTER_API_KEY=", source)
        self.assertIn("Settings drawer", source)


if __name__ == "__main__":
    unittest.main()
