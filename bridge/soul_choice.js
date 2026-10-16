// Records a person's answer to a card as ONE calibration atom in the AtomSpace
// (docs/milestones/M6_soul_base.md section A):
//
//   key  state:soul_choice:<card-id>
//   atom (soul-choice "<person>" "<kind>" "<card-id>" "<pick>" <at-ms>)
//
// One atom per card: a later pick or a dismissal after a pick is refused. If the
// AtomSpace service cannot be reached the record is queued in
// <iterDir>/.runtime/soul_choice_pending.jsonl and flushed, oldest first, by the
// next call that reaches the service. The person's answer reaches Iter through
// the chat bridge either way; this is only the durable record of it.
'use strict';

const fs = require('fs');
const net = require('net');
const path = require('path');

const PREFIX = 'state:soul_choice:';

function quote(value) {
  // Same encoding cognitive_events.metta_string uses for ordinary text.
  return JSON.stringify(String(value));
}

function atomFor(entry) {
  return `(soul-choice ${quote(entry.person)} ${quote(entry.kind)} ${quote(entry.cardId)} ${quote(entry.pick)} ${Math.trunc(Number(entry.at) || 0)})`;
}

function call(socketPath, method, params, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    if (!socketPath || !fs.existsSync(socketPath)) {
      const error = new Error('AtomSpace socket is not present');
      error.unreachable = true;
      reject(error);
      return;
    }
    const sock = net.createConnection(socketPath);
    let buffer = '';
    let done = false;
    const finish = (error, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { sock.destroy(); } catch (_) {}
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      const error = new Error(`AtomSpace ${method} timed out`);
      error.unreachable = true;
      finish(error);
    }, timeoutMs);
    sock.on('connect', () => sock.write(JSON.stringify({ method, params }) + '\n'));
    sock.on('data', (chunk) => {
      buffer += chunk.toString();
      const newline = buffer.indexOf('\n');
      if (newline < 0) return;
      try {
        const response = JSON.parse(buffer.slice(0, newline));
        if (!response.ok) finish(new Error(response.error || `AtomSpace ${method} failed`));
        else finish(null, response.result);
      } catch (error) {
        finish(error);
      }
    });
    sock.on('error', (error) => { error.unreachable = true; finish(error); });
  });
}

function pendingPath(iterDir) {
  return path.join(iterDir, '.runtime', 'soul_choice_pending.jsonl');
}

function readPending(iterDir) {
  try {
    return fs.readFileSync(pendingPath(iterDir), 'utf8').split('\n').filter(Boolean).map((line) => JSON.parse(line));
  } catch (_) {
    return [];
  }
}

function queue(iterDir, entry) {
  const file = pendingPath(iterDir);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.appendFileSync(file, JSON.stringify(entry) + '\n', { mode: 0o600 });
}

// Write one entry if its card has no record yet. Returns true when written.
async function writeOne(socketPath, entry) {
  const key = PREFIX + entry.cardId;
  const existing = await call(socketPath, 'read_atoms', { prefix: key });
  if (existing && existing.atoms && Object.prototype.hasOwnProperty.call(existing.atoms, key)) return false;
  try {
    await call(socketPath, 'transact', {
      operations: [{ op: 'upsert', key, atom: atomFor(entry) }],
      actor: 'person',
      source: 'sidebar',
      transaction_id: `soul-choice:${entry.cardId}`,
      expected_atoms: { [key]: null },
    });
  } catch (error) {
    // Lost a race with another click on the same card: the first one stands.
    if (/TransactionConflict|source beliefs changed|identity reused/.test(String(error.message))) return false;
    throw error;
  }
  return true;
}

async function flush(socketPath, iterDir) {
  const entries = readPending(iterDir);
  if (!entries.length) return 0;
  let written = 0;
  for (const entry of entries) if (await writeOne(socketPath, entry)) written += 1;
  fs.rmSync(pendingPath(iterDir), { force: true });
  return written;
}

// Flush queued choices (docs/milestones/M7_soul_personality.md A5): main.js calls
// this when the AtomSpace service reports ready, so a choice made while the
// service was down is recorded without waiting for the next click.
async function flushSoulChoices({ socket, iterDir }) {
  const pending = readPending(iterDir).length;
  if (!pending) return { flushed: 0 };
  await flush(socket, iterDir);
  return { flushed: pending };
}

// Forget what the Soul learned about one person (M7-A4): every taste belief and
// dismissal count for that person, in one transaction. Choices and seen markers
// stay, so the reducer never rebuilds a forgotten taste from old choices.
async function forgetSoulTaste({ socket, person }) {
  const who = String(person || '').trim().toLowerCase();
  if (!/^[a-z0-9_-]{1,40}$/.test(who)) throw new Error('forget needs a person');
  const keys = [];
  for (const prefix of [`state:soul_taste:${who}:`, `state:soul_dismiss:${who}:`]) {
    const result = await call(socket, 'read_atoms', { prefix });
    keys.push(...Object.keys((result && result.atoms) || {}));
  }
  if (keys.length) {
    await call(socket, 'transact', {
      operations: keys.map((key) => ({ op: 'remove', key })),
      actor: 'person',
      source: 'sidebar',
    });
  }
  return { deleted: keys.length };
}

async function recordSoulChoice({ socket, iterDir, person, kind, cardId, pick, at }) {
  const entry = {
    person: String(person || 'guest'),
    kind: String(kind || 'note'),
    cardId: String(cardId || ''),
    pick: String(pick || ''),
    at: Math.trunc(Number(at) || Date.now()),
  };
  if (!entry.cardId || !entry.pick) throw new Error('soul choice needs a card id and a pick');
  try {
    await flush(socket, iterDir);
    return { written: await writeOne(socket, entry) };
  } catch (error) {
    if (!error.unreachable) throw error;
    // Never queue a second answer for a card already waiting in the queue.
    if (!readPending(iterDir).some((queued) => queued.cardId === entry.cardId)) queue(iterDir, entry);
    return { written: false, queued: true };
  }
}

// One atom per margin request (docs/milestones/M8_soul_presence.md D3), so the dashboard can
// count them from the authority. No queue: a miss is only a log line in main.js.
async function recordSoulMargin({ socket, person, app, intent, messageId, at }) {
  const id = String(messageId || '');
  if (!/^[A-Za-z0-9_.-]{1,160}$/.test(id)) throw new Error('margin record needs a message id');
  const atom = `(soul-margin ${quote(person || 'guest')} ${quote(app || '')} ${quote(intent || '')} ${Math.trunc(Number(at) || Date.now())})`;
  try {
    await call(socket, 'transact', {
      operations: [{ op: 'upsert', key: `state:soul_margin:${id}`, atom }],
      actor: 'person',
      source: 'margin',
    });
  } catch (error) {
    if (error.unreachable) return { written: false };
    throw error;
  }
  return { written: true };
}

module.exports = { recordSoulChoice, flushSoulChoices, forgetSoulTaste, recordSoulMargin, atomFor, PREFIX };
