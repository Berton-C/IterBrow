// File-based chat bridge between the Electron sidebar UI and Iter's own
// channels/electron_ui.py. Follows Iter's own documented channel
// convention (a channel exposes receive()/send(); if it needs a
// standing connection it manages its own runtime state — see
// channels/_example.py) — the difference here is Electron's main
// process is already the long-lived side, so no separate Python daemon
// is needed at all. Both sides just watch a shared directory:
//
//   inbox/  — files written by Electron (your typed messages) —
//             read + deleted by electron_ui.py's receive(), polled by
//             Iter's main loop every cycle.
//   outbox/ — files written by electron_ui.py's send() (via Iter's
//             `send` tool) — watched + deleted by Electron, shown in
//             the chat panel.
const fs = require('fs');
const path = require('path');

function makeChatBridge(iterRoot, onIncoming) {
  const runtimeDir = path.join(iterRoot, '.runtime', 'electron_ui');
  const inboxDir = path.join(runtimeDir, 'inbox');
  const outboxDir = path.join(runtimeDir, 'outbox');
  fs.mkdirSync(inboxDir, { recursive: true });
  fs.mkdirSync(outboxDir, { recursive: true });

  function sendToIter(content) {
    const file = path.join(inboxDir, `${process.hrtime.bigint()}.txt`);
    fs.writeFileSync(file, content, 'utf8');
  }

  function pollOutbox() {
    let names = [];
    try {
      names = fs.readdirSync(outboxDir).sort();
    } catch (_) {
      return;
    }
    for (const name of names) {
      const full = path.join(outboxDir, name);
      try {
        const content = fs.readFileSync(full, 'utf8');
        fs.unlinkSync(full);
        onIncoming(content);
      } catch (_) {
        /* file may have been picked up already */
      }
    }
  }

  const timer = setInterval(pollOutbox, 400);
  return {
    sendToIter,
    stop: () => clearInterval(timer),
  };
}

module.exports = { makeChatBridge };
