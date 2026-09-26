#!/usr/bin/env python3
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChatBridgeTests(unittest.TestCase):
    def test_queue_delivery_is_durable_replayable_and_deduplicated(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            script = textwrap.dedent(
                f"""
                const fs = require('fs');
                const path = require('path');
                const {{ makeChatBridge }} = require({json.dumps(str(ROOT / 'bridge' / 'chat_bridge.js'))});
                const iterRoot = {json.dumps(temporary)};
                const received = [];
                const logs = [];
                const first = makeChatBridge(iterRoot, (message) => received.push(message), {{
                  pollIntervalMs: 60000,
                  settleMs: 0,
                  log: (line) => logs.push(line),
                }});

                const user = first.sendToIter('  durable hello  ');
                const inboxNames = fs.readdirSync(first.paths.inboxDir);
                const inboxBody = fs.readFileSync(path.join(first.paths.inboxDir, inboxNames[0]), 'utf8');

                const legacyPath = path.join(first.paths.outboxDir, 'legacy.txt');
                fs.writeFileSync(legacyPath, 'legacy reply');
                fs.utimesSync(legacyPath, new Date(0), new Date(0));
                first.pollNow();
                const legacy = received[0];

                const envelope = {{
                  schema_version: 1,
                  id: 'iter-stable-id',
                  role: 'iter',
                  content: 'enveloped reply',
                  at: 42,
                }};
                const envelopePath = path.join(first.paths.outboxDir, 'envelope.json');
                fs.writeFileSync(envelopePath, JSON.stringify(envelope));
                fs.utimesSync(envelopePath, new Date(0), new Date(0));
                first.pollNow();
                const duplicatePath = path.join(first.paths.outboxDir, 'duplicate.json');
                fs.writeFileSync(duplicatePath, JSON.stringify(envelope));
                fs.utimesSync(duplicatePath, new Date(0), new Date(0));
                first.pollNow();
                const firstHistory = first.history();
                first.stop();

                fs.appendFileSync(first.paths.journalPath, '{{"incomplete"');
                const replayed = [];
                const second = makeChatBridge(iterRoot, (message) => replayed.push(message), {{
                  pollIntervalMs: 60000,
                  settleMs: 0,
                  log: (line) => logs.push(line),
                }});
                const secondHistory = second.history();
                const recoveredTail = fs.readdirSync(second.paths.recoveryDir)
                  .some((name) => name.startsWith('messages.incomplete-'));
                second.stop();

                console.log(JSON.stringify({{
                  user,
                  inboxNames,
                  inboxBody,
                  legacy,
                  receivedCount: received.length,
                  firstHistory,
                  secondHistory,
                  recoveredTail,
                  logs,
                  outboxNames: fs.readdirSync(first.paths.outboxDir),
                }}));
                """
            )
            result = subprocess.run(
                ["node", "-e", script],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            self.assertEqual(observed["user"]["content"], "durable hello")
            self.assertEqual(observed["inboxBody"], "durable hello")
            self.assertEqual(len(observed["inboxNames"]), 1)
            self.assertEqual(observed["legacy"]["content"], "legacy reply")
            self.assertEqual(observed["receivedCount"], 2)
            self.assertEqual(len(observed["firstHistory"]), 3)
            self.assertEqual(observed["firstHistory"], observed["secondHistory"])
            self.assertTrue(observed["recoveredTail"])
            self.assertEqual(observed["outboxNames"], [])
            self.assertTrue(any("recovered incomplete journal tail" in line
                                for line in observed["logs"]))

    def test_sidebar_replays_stable_message_ids(self):
        preload = (ROOT / "preload.js").read_text(encoding="utf-8")
        renderer = (ROOT / "renderer" / "renderer.js").read_text(encoding="utf-8")
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        self.assertIn("chatHistory: () => ipcRenderer.invoke('chat:history')", preload)
        self.assertIn("window.iterApi.onChatIncoming(mergeChatMessage)", renderer)
        self.assertIn("function syncChatHistory()", renderer)
        self.assertIn("function syncSidebarState()", renderer)
        self.assertIn("window.addEventListener('focus', syncSidebarState)", renderer)
        self.assertIn("document.addEventListener('visibilitychange'", renderer)
        self.assertIn("window.iterApi.onUiResume(syncSidebarState)", renderer)
        self.assertIn("if (chatHistorySyncInFlight) return chatHistorySyncInFlight", renderer)
        self.assertIn("if (existing", renderer)
        self.assertLess(
            renderer.index("window.iterApi.onChatIncoming(mergeChatMessage)"),
            renderer.index("function syncChatHistory()"),
        )
        self.assertIn("ipcMain.handle('chat:history'", main)
        self.assertIn("onUiResume: (cb) => ipcRenderer.on('ui:resume'", preload)
        self.assertIn("powerMonitor.on('unlock-screen'", main)
        self.assertIn("powerMonitor.on('resume'", main)
        self.assertIn("win.on('focus', () => reconcileSidebarAfterSystemResume('window-focus'))", main)
        self.assertIn("win.on('show', () => reconcileSidebarAfterSystemResume('window-show'))", main)
        self.assertIn("backgroundThrottling: false", main)
        self.assertIn("win.contentView.addChildView(view)", main)
        self.assertNotIn("view.setVisible(false)", main)
        self.assertIn("view.webContents.invalidate()", main)


if __name__ == "__main__":
    unittest.main()
