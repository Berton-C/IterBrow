#!/usr/bin/env python3
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PWQBoardBoundaryTests(unittest.TestCase):
    def test_board_has_no_whole_projection_write_capability(self):
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        preload = (ROOT / "bridge" / "pwq_preload.js").read_text(encoding="utf-8")
        board = (ROOT / "iter" / "pwq.html").read_text(encoding="utf-8")
        tool = (ROOT / "iter" / "tools" / "pwq_write.py").read_text(encoding="utf-8")

        self.assertNotIn("ipcMain.handle('pwq:write'", main)
        self.assertNotIn("fsWrite:", preload)
        self.assertNotIn("async function save()", board)
        self.assertNotIn("await save()", board)
        self.assertNotIn("localStorage", board)
        self.assertIn("write/sync is reserved for explicit offline migration", tool)
        self.assertNotIn("STORE.sync_board(payload", tool)
        service = (ROOT / "iter" / "pwq_service.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.get("ITER_DIR")', service)

    def test_every_board_mutation_uses_a_narrow_protocol_command(self):
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        preload = (ROOT / "bridge" / "pwq_preload.js").read_text(encoding="utf-8")
        board = (ROOT / "iter" / "pwq.html").read_text(encoding="utf-8")

        self.assertIn("pwqRead:", preload)
        self.assertIn("pwqCommand:", preload)
        for action in (
            "sign", "modify", "reject", "reorder", "pause", "resume", "complete",
        ):
            self.assertIn("'" + action + "'", main)
            self.assertIn("protocolCommand('" + action + "'", board)

    def test_inline_board_script_is_valid_and_legacy_history_is_renderable(self):
        board = (ROOT / "iter" / "pwq.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", board, re.I | re.S)
        self.assertEqual(len(scripts), 1)
        self.assertIn("if (typeof e === 'string')", scripts[0])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", dir="/private/tmp", encoding="utf-8"
        ) as handle:
            handle.write(scripts[0])
            handle.flush()
            result = subprocess.run(
                ["node", "--check", handle.name],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_live_refresh_is_read_only_sequence_gated_and_preserves_view_state(self):
        board = (ROOT / "iter" / "pwq.html").read_text(encoding="utf-8")

        self.assertIn("const LIVE_REFRESH_MS = 2000;", board)
        self.assertIn("nextSequence === lastRenderedSequence", board)
        self.assertIn("setInterval(() => load('interval'), LIVE_REFRESH_MS)", board)
        self.assertIn("window.addEventListener('focus', () => load('focus'))", board)
        self.assertIn("document.addEventListener('visibilitychange'", board)
        self.assertIn("document.visibilityState === 'visible'", board)

        for preserved_state in (
            "captureViewState",
            "restoreViewState",
            "drafts",
            "selectionStart",
            "selectionEnd",
            "window.scrollX",
            "window.scrollY",
            "filter",
            "preventScroll: true",
        ):
            self.assertIn(preserved_state, board)

        refresh_start = board.index("async function load(")
        refresh_end = board.index("function showBell", refresh_start)
        refresh_path = board[refresh_start:refresh_end]
        self.assertIn("window.iterApi.pwqRead()", refresh_path)
        self.assertNotIn("protocolCommand", refresh_path)
        self.assertNotIn("pwqCommand", refresh_path)


if __name__ == "__main__":
    unittest.main()
