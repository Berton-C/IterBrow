// Narrow collaboration contract for navigation-locked IterBrow tab/apps.
// The main process independently resolves the same scope from WebContents;
// these arguments identify the consumer to this isolated renderer only.
const { contextBridge, ipcRenderer } = require('electron');

function argument(name) {
  const prefix = `--${name}=`;
  const found = process.argv.find((value) => value.startsWith(prefix));
  if (!found) throw new Error(`Missing application scope: ${name}`);
  return found.slice(prefix.length);
}

const appId = argument('iter-app-id');
const consumerId = argument('iter-consumer-id');

// Page-local diagnostics only: no record values, journal, polling or replay.
// A backend receipt establishes acceptance, not a functioning save/reopen UI.
let contextReads = 0;
let pendingCommands = 0;
let lastContext = null;
let lastContextAttempt = null;
const commands = [];
function label(value) { return typeof value === 'string' ? value.slice(0, 128) : null; }

async function appContext() {
  contextReads += 1;
  const attempt = { read_number: contextReads, started_at: new Date().toISOString(), state: 'pending' };
  lastContextAttempt = attempt;
  try {
    const result = await ipcRenderer.invoke('app:context');
    attempt.state = 'returned';
    if (result && typeof result === 'object'
        && (!lastContext || attempt.read_number >= lastContext.read_number)) {
      lastContext = {
        read_number: attempt.read_number, observed_at: new Date().toISOString(), epoch: label(result.epoch),
        revision: result.revision, commit: result.commit,
        collections: Object.entries(result.records || {}).map(([name, records]) => ({
          name, count: Array.isArray(records) ? records.length : null,
        })),
      };
    }
    return result;
  } catch (error) {
    attempt.state = 'failed';
    attempt.error = String(error).slice(0, 240);
    throw error;
  } finally {
    attempt.finished_at = new Date().toISOString();
  }
}

async function appCommand(command) {
  const entry = {
    command_id: label(command && command.command_id),
    type: label(command && command.type), collection: label(command && command.collection),
    record_id: label(command && ((command.record && command.record.id) || command.record_id)),
    started_at: new Date().toISOString(), state: 'pending',
  };
  commands.push(entry);
  if (commands.length > 8) commands.shift();
  pendingCommands += 1;
  try {
    const result = await ipcRenderer.invoke('app:command', command);
    entry.state = result && result.app_id === appId && entry.command_id && result.command_id === entry.command_id
      && Number.isSafeInteger(result.revision) && result.revision >= 0
      && Number.isSafeInteger(result.commit) && result.commit >= 0
      ? 'acknowledged' : 'returned_without_receipt';
    if (entry.state === 'acknowledged') {
      entry.revision = result.revision;
      entry.commit = result.commit;
      entry.duplicate = result.duplicate === true;
    }
    return result;
  } catch (error) {
    entry.state = 'rejected_or_unconfirmed';
    entry.error = String(error).slice(0, 240);
    throw error;
  } finally {
    entry.finished_at = new Date().toISOString();
    pendingCommands -= 1;
  }
}

function storageStatus() {
  return JSON.parse(JSON.stringify({
    app_id: appId, consumer_id: consumerId,
    scope: 'All views of this app share its app_id; collections accept arbitrary valid identifiers.',
    context_reads: contextReads, pending_commands: pendingCommands,
    last_context: lastContext, last_context_attempt: lastContextAttempt, recent_commands: commands,
    notice: 'This page session only. No receipt means no acknowledged backend write was observed. '
      + 'A receipt does not prove the UI sent the intended values or reloads them correctly. '
      + 'Verify the feature by saving and reopening it; no command is repeated by these diagnostics.',
  }));
}

contextBridge.exposeInMainWorld('iterApp', Object.freeze({
  appContext,
  appCommand,
  storageStatus,
  appChanges: (afterCommit) => ipcRenderer.invoke('app:changes', afterCommit),
  subscribe: (afterCommit) => ipcRenderer.invoke('app:changes', afterCommit),
}));
