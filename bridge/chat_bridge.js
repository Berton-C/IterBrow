// Durable file bridge between the Electron sidebar and Iter's
// channels/electron_ui.py.
//
// Queue files remain the compatibility boundary with the cognition process,
// but they are no longer the UI's only copy of a message. The Electron main
// process records every accepted user/Iter message in an append-only journal
// before an outbox file is acknowledged. A sidebar reload or an IPC-listener
// race can therefore replay the conversation instead of losing it.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const SCHEMA_VERSION = 1;
const DEFAULT_HISTORY_LIMIT = 500;

function messageId(role) {
  return `${role}-${Date.now()}-${process.hrtime.bigint()}-${crypto.randomUUID()}`;
}

function validMessage(value) {
  return value && typeof value === 'object'
    && typeof value.id === 'string' && value.id
    && (value.role === 'user' || value.role === 'iter')
    && typeof value.content === 'string';
}

function makeChatBridge(iterRoot, onIncoming, options = {}) {
  const log = typeof options.log === 'function' ? options.log : () => {};
  const pollIntervalMs = Number.isFinite(options.pollIntervalMs)
    ? options.pollIntervalMs : 200;
  const settleMs = Number.isFinite(options.settleMs) ? options.settleMs : 100;
  const historyLimit = Number.isFinite(options.historyLimit)
    ? options.historyLimit : DEFAULT_HISTORY_LIMIT;

  const runtimeDir = path.join(iterRoot, '.runtime', 'electron_ui');
  const inboxDir = path.join(runtimeDir, 'inbox');
  const outboxDir = path.join(runtimeDir, 'outbox');
  const stagingDir = path.join(runtimeDir, 'staging');
  const recoveryDir = path.join(runtimeDir, 'recovery');
  const journalPath = path.join(runtimeDir, 'messages.jsonl');
  fs.mkdirSync(inboxDir, { recursive: true });
  fs.mkdirSync(outboxDir, { recursive: true });
  fs.mkdirSync(stagingDir, { recursive: true });
  fs.mkdirSync(recoveryDir, { recursive: true });

  function repairIncompleteTail() {
    if (!fs.existsSync(journalPath)) return;
    const bytes = fs.readFileSync(journalPath);
    if (!bytes.length || bytes[bytes.length - 1] === 0x0a) return;
    const lastNewline = bytes.lastIndexOf(0x0a);
    const keep = lastNewline < 0 ? 0 : lastNewline + 1;
    const tail = bytes.subarray(keep);
    const recoveryPath = path.join(
      recoveryDir,
      `messages.incomplete-${Date.now()}-${crypto.randomUUID()}.json`,
    );
    fs.writeFileSync(recoveryPath, tail);
    fs.truncateSync(journalPath, keep);
    log(`[chat] recovered incomplete journal tail to ${recoveryPath}`);
  }

  repairIncompleteTail();

  const messages = [];
  const seen = new Set();
  if (fs.existsSync(journalPath)) {
    const lines = fs.readFileSync(journalPath, 'utf8').split('\n');
    for (let index = 0; index < lines.length; index += 1) {
      if (!lines[index]) continue;
      try {
        const message = JSON.parse(lines[index]);
        if (!validMessage(message)) throw new Error('invalid message envelope');
        if (!seen.has(message.id)) {
          seen.add(message.id);
          messages.push(message);
        }
      } catch (error) {
        // Chat history is a replay aid, not cognitive authority. Preserve the
        // journal and keep the live channel available while surfacing damage.
        log(`[chat] ignored malformed journal record ${index + 1}: ${error.message}`);
      }
    }
  }

  function appendMessage(message) {
    if (!validMessage(message)) throw new Error('invalid chat message envelope');
    if (seen.has(message.id)) return false;
    const descriptor = fs.openSync(journalPath, 'a', 0o600);
    try {
      fs.writeSync(descriptor, `${JSON.stringify(message)}\n`, null, 'utf8');
      fs.fsyncSync(descriptor);
    } finally {
      fs.closeSync(descriptor);
    }
    seen.add(message.id);
    messages.push(message);
    return true;
  }

  function writeQueueAtomically(directory, filename, content) {
    const temporary = path.join(
      stagingDir,
      `${filename}.${process.pid}.${crypto.randomUUID()}.tmp`,
    );
    const destination = path.join(directory, filename);
    fs.writeFileSync(temporary, content, { encoding: 'utf8', flag: 'wx', mode: 0o600 });
    fs.renameSync(temporary, destination);
    return destination;
  }

  function sendToIter(content) {
    const text = String(content == null ? '' : content).trim();
    if (!text) throw new Error('chat message is empty');
    const message = {
      schema_version: SCHEMA_VERSION,
      id: messageId('user'),
      role: 'user',
      content: text,
      at: Date.now(),
    };
    // The live generation may still use the original plain-text receiver, so
    // retain that queue payload while making its publication atomic.
    writeQueueAtomically(inboxDir, `${message.id}.txt`, text);
    appendMessage(message);
    return message;
  }

  function decodeOutbox(name, raw) {
    try {
      const decoded = JSON.parse(raw);
      if (decoded && decoded.schema_version === SCHEMA_VERSION
          && typeof decoded.content === 'string') {
        return {
          schema_version: SCHEMA_VERSION,
          id: String(decoded.id || `iter-file-${name}`),
          role: 'iter',
          content: decoded.content,
          at: Number(decoded.at) || Date.now(),
        };
      }
    } catch (_) {
      // Legacy generations write plain text; they remain supported.
    }
    return {
      schema_version: SCHEMA_VERSION,
      id: `iter-file-${name}`,
      role: 'iter',
      content: raw,
      at: Date.now(),
    };
  }

  function pollOutbox() {
    let names = [];
    try {
      names = fs.readdirSync(outboxDir).filter((name) => !name.startsWith('.')).sort();
    } catch (error) {
      log(`[chat] cannot inspect outbox: ${error.message}`);
      return;
    }
    for (const name of names) {
      const full = path.join(outboxDir, name);
      try {
        const stat = fs.statSync(full);
        if (!stat.isFile() || Date.now() - stat.mtimeMs < settleMs) continue;
        const raw = fs.readFileSync(full, 'utf8');
        if (!raw) continue;
        const message = decodeOutbox(name, raw);
        const isNew = appendMessage(message);
        // Journal durability is the acknowledgement boundary. Only after the
        // append is synced may the transient queue file be removed.
        fs.unlinkSync(full);
        if (isNew) onIncoming(message);
      } catch (error) {
        // Keep an unacknowledged queue file for the next poll. Never turn a
        // transient read/journal/renderer failure into silent message loss.
        log(`[chat] retained outbox item ${name}: ${error.message}`);
      }
    }
  }

  const timer = setInterval(pollOutbox, pollIntervalMs);
  return {
    sendToIter,
    history: () => messages.slice(-historyLimit).map((message) => ({ ...message })),
    pollNow: pollOutbox,
    paths: { runtimeDir, inboxDir, outboxDir, stagingDir, recoveryDir, journalPath },
    stop: () => clearInterval(timer),
  };
}

module.exports = { makeChatBridge };
