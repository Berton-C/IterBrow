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

// Interactive cards (docs/milestones/M6_soul_base.md section A). A card rides
// on an ordinary Iter message whose `content` is the markdown fallback, so an
// older sidebar, the journal and the transcript still read it as text.
const CARD_KINDS = new Set(['fork', 'brief', 'read', 'offer', 'note']);
const PATTERN_ID = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
const MUSEUM_ID = /^[A-Za-z0-9_.-]{1,64}$/;

function nonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

// Returns a clean copy of a valid card, or null.
function validCard(card) {
  if (!card || typeof card !== 'object' || Array.isArray(card)) return null;
  if (!nonEmptyString(card.id) || !CARD_KINDS.has(card.kind) || !nonEmptyString(card.title)) return null;
  if (card.body !== undefined && typeof card.body !== 'string') return null;
  if (!Array.isArray(card.choices) || card.choices.length < 1 || card.choices.length > 3) return null;
  const choices = [];
  const ids = new Set();
  for (const choice of card.choices) {
    if (!choice || !nonEmptyString(choice.id) || !nonEmptyString(choice.label) || ids.has(choice.id)) return null;
    if (choice.id === 'dismiss') return null; // reserved for the dismiss control
    if (choice.hint !== undefined && typeof choice.hint !== 'string') return null;
    ids.add(choice.id);
    const item = { id: choice.id, label: choice.label, ...(choice.hint ? { hint: choice.hint } : {}) };
    // M7 metadata: kept when well formed, dropped (never fatal) otherwise.
    if (typeof choice.pattern === 'string' && PATTERN_ID.test(choice.pattern)) item.pattern = choice.pattern;
    if (typeof choice.museum_id === 'string' && MUSEUM_ID.test(choice.museum_id)) item.museum_id = choice.museum_id;
    choices.push(item);
  }
  const clean = { id: card.id, kind: card.kind, title: card.title, body: card.body || '', choices };
  if (card.links !== undefined) {
    if (!Array.isArray(card.links) || card.links.length > 3) return null;
    const links = [];
    for (const link of card.links) {
      if (!link || !nonEmptyString(link.label) || typeof link.url !== 'string' || !/^https?:\/\//i.test(link.url)) return null;
      links.push({ label: link.label, url: link.url });
    }
    if (links.length) clean.links = links;
  }
  if (card.expires_at !== undefined) {
    if (!Number.isFinite(Number(card.expires_at))) return null;
    clean.expires_at = Number(card.expires_at);
  }
  return clean;
}

// A request from inside an app tab (docs/milestones/M8_soul_presence.md D3). Iter reads
// `[margin app=<app> tab=<id> intent=<ask|jam> element=<selector|page>] <text>`.
const MARGIN_INTENTS = new Set(['ask', 'jam']);
const MARGIN_APP = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

function cleanMargin(payload) {
  const value = payload && typeof payload === 'object' ? payload : {};
  if (!MARGIN_INTENTS.has(value.intent)) throw new Error('margin intent must be ask or jam');
  if (typeof value.app !== 'string' || !MARGIN_APP.test(value.app)) throw new Error('margin app is invalid');
  if (!Number.isInteger(value.tab) || value.tab < 0) throw new Error('margin tab is invalid');
  if (value.text !== undefined && typeof value.text !== 'string') throw new Error('margin text must be a string');
  const text = String(value.text || '').trim();
  if (value.intent === 'ask' && !text) throw new Error('say what you would like to ask');
  let element = null;
  if (value.element !== undefined && value.element !== null) {
    const raw = value.element;
    if (typeof raw !== 'object' || typeof raw.selector !== 'string' || !raw.selector.trim() || raw.selector.length > 200) {
      throw new Error('margin element is invalid');
    }
    element = { selector: raw.selector.replace(/[\]\r\n]/g, ' ').trim() };
    if (typeof raw.tag === 'string') element.tag = raw.tag.slice(0, 40);
    if (typeof raw.text === 'string') element.text = raw.text.slice(0, 80);
  }
  return { app: value.app, tab: value.tab, intent: value.intent, text, element };
}

function marginLine(payload) {
  const where = payload.element && payload.element.selector ? payload.element.selector : 'page';
  const head = `[margin app=${payload.app} tab=${payload.tab} intent=${payload.intent} element=${where}]`;
  const text = String(payload.text || '').trim();
  return text ? `${head} ${text}` : head;
}

function choiceLine(cardId, pick, person, label) {
  const head = `[choice card=${cardId} pick=${pick} by=${person}]`;
  return pick === 'dismiss' || !label ? head : `${head} ${label}`;
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
  function loadJournal() {
  messages.length = 0;
  seen.clear();
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
  }
  loadJournal();

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
    // Reset/Import may have removed the queue folders while the window stayed open.
    fs.mkdirSync(stagingDir, { recursive: true, mode: 0o700 });
    fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
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

  // A person's answer to a card. Iter receives the line like any user
  // message (the plain-text inbox stays the compatibility boundary); the
  // journal also keeps the structured pick so a reloaded sidebar shows the
  // card as answered. `person` comes from main.js (soul settings), never
  // from the renderer.
  function sendChoice(cardId, pick, person, label = '') {
    if (!nonEmptyString(cardId) || !nonEmptyString(pick)) throw new Error('choice needs a card and a pick');
    const who = nonEmptyString(person) ? String(person).trim() : 'guest';
    const text = choiceLine(String(cardId).trim(), String(pick).trim(), who, String(label || '').trim());
    const message = {
      schema_version: SCHEMA_VERSION,
      id: messageId('user'),
      role: 'user',
      content: text,
      at: Date.now(),
      choice: { card: String(cardId).trim(), pick: String(pick).trim(), by: who },
    };
    writeQueueAtomically(inboxDir, `${message.id}.txt`, text);
    appendMessage(message);
    return message;
  }

  // A margin request from an app tab. main.js has already checked the tab (app scope, lock)
  // and the person's switch; the payload is validated again here.
  function sendMargin(payload) {
    const clean = cleanMargin(payload);
    const text = marginLine(clean);
    const message = {
      schema_version: SCHEMA_VERSION,
      id: messageId('user'),
      role: 'user',
      content: text,
      at: Date.now(),
      margin: { app: clean.app, tab: clean.tab, intent: clean.intent, element: clean.element },
    };
    writeQueueAtomically(inboxDir, `${message.id}.txt`, text);
    appendMessage(message);
    return message;
  }

  function decodeOutbox(name, raw) {
    try {
      const decoded = JSON.parse(raw);
      if (decoded && decoded.schema_version === SCHEMA_VERSION
          && typeof decoded.content === 'string') {
        const message = {
          schema_version: SCHEMA_VERSION,
          id: String(decoded.id || `iter-file-${name}`),
          role: 'iter',
          content: decoded.content,
          at: Number(decoded.at) || Date.now(),
        };
        // A felt note (docs/milestones/M7_soul_personality.md B1): only `true` is kept.
        if (decoded.felt === true) message.felt = true;
        if (decoded.card !== undefined) {
          const card = validCard(decoded.card);
          if (card) message.card = card;
          else log(`[chat] dropped malformed card in ${name}; delivering its text only`);
        }
        return message;
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
    sendChoice,
    sendMargin,
    history: () => messages.slice(-historyLimit).map((message) => ({ ...message })),
    pollNow: pollOutbox,
    // Re-read the journal after Reset (file removed) or Restore (file replaced).
    reload: () => { repairIncompleteTail(); loadJournal(); return messages.length; },
    paths: { runtimeDir, inboxDir, outboxDir, stagingDir, recoveryDir, journalPath },
    stop: () => clearInterval(timer),
  };
}

module.exports = { makeChatBridge, validCard, choiceLine, marginLine };
