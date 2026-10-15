const chat = document.getElementById('chat');
const chatInput = document.getElementById('chat-input');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const logView = document.getElementById('log-view');

// Tab strip and its rendering/drag/pin/lock/close logic moved out of this
// sidebar entirely on 2026-09-17 into its own full-width view -- see
// renderer/tabstrip.html + tabstrip.js -- for the same reason the nav
// toolbar moved out below: this column is too narrow to hold them.

// Back/forward/reload/address-bar/Go/Dashboards controls now live in the
// dedicated full-width toolbar view (renderer/toolbar.html + toolbar.js),
// which sits directly above the browsed page like a normal browser's nav
// bar, instead of being crammed into this sidebar. See main.js's
// toolbarView.

// Still used below by the Tab Groups panel, even though the tab strip
// itself moved out to tabstrip.js.
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------
const chatMessages = new Map();
let transientChatSequence = 0;

// Messages are laid out the way Mattermost lays them out: left-aligned, an
// author line with the time, the body rendered from Markdown, and consecutive
// messages from the same author within a few minutes collapse under one
// author line. System notes stay small and quiet.
const AUTHOR_LABEL = { user: 'You', iter: 'Iter', sys: '' };
const GROUP_WINDOW_MS = 5 * 60 * 1000;

function formatTime(at) {
  const date = new Date(Number(at) || Date.now());
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return sameDay ? time : date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + time;
}

function renderChatMessages() {
  const stickToBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 40;
  chat.textContent = '';
  const ordered = Array.from(chatMessages.values()).sort((left, right) => {
    const timeDifference = Number(left.at || 0) - Number(right.at || 0);
    return timeDifference || String(left.id).localeCompare(String(right.id));
  });
  let previous = null;
  for (const message of ordered) {
    const row = document.createElement('div');
    row.className = 'msg ' + message.role;
    const continues = previous && previous.role === message.role && message.role !== 'sys'
      && Math.abs(Number(message.at || 0) - Number(previous.at || 0)) < GROUP_WINDOW_MS;
    if (continues) row.classList.add('continued');
    if (message.role !== 'sys' && !continues) {
      const head = document.createElement('div');
      head.className = 'author-line';
      const author = document.createElement('span');
      author.className = 'author';
      author.textContent = AUTHOR_LABEL[message.role] || message.role;
      const time = document.createElement('time');
      time.textContent = formatTime(message.at);
      time.title = new Date(Number(message.at) || Date.now()).toLocaleString();
      head.append(author, time);
      row.appendChild(head);
    }
    const body = document.createElement('div');
    body.className = 'body' + (message.role === 'sys' ? '' : ' markdown');
    if (message.role === 'sys') body.textContent = message.content;
    else body.innerHTML = window.IterMarkdown.render(message.content);
    row.appendChild(body);
    chat.appendChild(row);
    previous = message;
  }
  if (stickToBottom) chat.scrollTop = chat.scrollHeight;
}

// Links in chat open as browser tabs; the sidebar itself never navigates.
chat.addEventListener('click', (event) => {
  const anchor = event.target.closest('a[href]');
  if (!anchor || !chat.contains(anchor)) return;
  event.preventDefault();
  const href = window.IterMarkdown.safeHref(anchor.getAttribute('href'));
  if (href && /^https?:/i.test(href)) window.iterApi.newTab(href);
});

function mergeChatMessage(message) {
  const normalized = typeof message === 'string'
    ? {
        id: `legacy-${Date.now()}-${transientChatSequence += 1}`,
        role: 'iter',
        content: message,
        at: Date.now(),
      }
    : message;
  if (!normalized || !normalized.id || typeof normalized.content !== 'string') return;
  if (!['user', 'iter', 'sys'].includes(normalized.role)) return;
  const id = String(normalized.id);
  const existing = chatMessages.get(id);
  if (existing
      && existing.role === normalized.role
      && existing.content === normalized.content
      && Number(existing.at || 0) === Number(normalized.at || 0)) return false;
  chatMessages.set(id, normalized);
  renderChatMessages();
  return true;
}

function mergeChatHistory(history) {
  let changed = false;
  for (const message of history) {
    const normalized = typeof message === 'string'
      ? {
          id: `legacy-${Date.now()}-${transientChatSequence += 1}`,
          role: 'iter',
          content: message,
          at: Date.now(),
        }
      : message;
    if (!normalized || !normalized.id || typeof normalized.content !== 'string') continue;
    if (!['user', 'iter', 'sys'].includes(normalized.role)) continue;
    const id = String(normalized.id);
    const existing = chatMessages.get(id);
    if (existing
        && existing.role === normalized.role
        && existing.content === normalized.content
        && Number(existing.at || 0) === Number(normalized.at || 0)) continue;
    chatMessages.set(id, normalized);
    changed = true;
  }
  if (changed || !chatMessages.size) renderChatMessages();
}

// After Reset or Restore the saved chat changed underneath us: drop what is
// on screen and replay the journal as it is now.
function replaceChatFromHistory() {
  chatMessages.clear();
  renderChatMessages();
  return syncChatHistory();
}

function addMessage(role, text) {
  mergeChatMessage({
    id: `local-${Date.now()}-${transientChatSequence += 1}`,
    role,
    content: String(text),
    at: Date.now(),
  });
}

document.getElementById('btn-send').addEventListener('click', sendChat);

// ---------------------------------------------------------------------
// Composer formatting (Mattermost-style): the text box takes Markdown, the
// bar inserts the markup around the selection, and Preview shows the
// rendered result in place of the box without sending anything.
// ---------------------------------------------------------------------
const composerPreview = document.getElementById('composer-preview');
const btnPreview = document.getElementById('btn-preview');

function wrapSelection(before, after, placeholder) {
  const start = chatInput.selectionStart;
  const end = chatInput.selectionEnd;
  const value = chatInput.value;
  const selected = value.slice(start, end);
  const already = value.slice(Math.max(0, start - before.length), start) === before
    && value.slice(end, end + after.length) === after;
  if (already && selected) {
    chatInput.value = value.slice(0, start - before.length) + selected + value.slice(end + after.length);
    chatInput.setSelectionRange(start - before.length, end - before.length);
  } else {
    const text = selected || placeholder;
    chatInput.value = value.slice(0, start) + before + text + after + value.slice(end);
    chatInput.setSelectionRange(start + before.length, start + before.length + text.length);
  }
  chatInput.focus();
  chatInput.dispatchEvent(new Event('input'));
}

function prefixLines(prefixFor) {
  const value = chatInput.value;
  const start = value.lastIndexOf('\n', chatInput.selectionStart - 1) + 1;
  let end = value.indexOf('\n', chatInput.selectionEnd);
  if (end === -1) end = value.length;
  const block = value.slice(start, end);
  const lines = block.split('\n');
  const allPrefixed = lines.every((line, index) => line.startsWith(prefixFor(index, true)));
  const changed = lines.map((line, index) => (allPrefixed
    ? line.slice(prefixFor(index, true).length)
    : prefixFor(index) + line)).join('\n');
  chatInput.value = value.slice(0, start) + changed + value.slice(end);
  chatInput.setSelectionRange(start, start + changed.length);
  chatInput.focus();
  chatInput.dispatchEvent(new Event('input'));
}

const FORMATS = {
  bold: () => wrapSelection('**', '**', 'bold text'),
  italic: () => wrapSelection('_', '_', 'italic text'),
  strike: () => wrapSelection('~~', '~~', 'struck text'),
  code: () => {
    const selected = chatInput.value.slice(chatInput.selectionStart, chatInput.selectionEnd);
    if (selected.includes('\n')) wrapSelection('```\n', '\n```', 'code');
    else wrapSelection('`', '`', 'code');
  },
  link: () => {
    const selected = chatInput.value.slice(chatInput.selectionStart, chatInput.selectionEnd);
    if (/^https?:\/\//i.test(selected)) wrapSelection('[', '](' + selected + ')', 'link text');
    else wrapSelection('[', '](https://)', selected || 'link text');
  },
  heading: () => prefixLines(() => '### '),
  quote: () => prefixLines(() => '> '),
  bullet: () => prefixLines(() => '- '),
  number: () => prefixLines((index, probe) => (probe ? '1. ' : (index + 1) + '. ')),
};

document.getElementById('format-bar').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-format]');
  if (!button) return;
  event.preventDefault();
  if (composerPreview.hidden === false) togglePreview(false);
  FORMATS[button.dataset.format]();
});

function togglePreview(force) {
  const show = typeof force === 'boolean' ? force : composerPreview.hidden;
  if (show) {
    composerPreview.innerHTML = chatInput.value.trim()
      ? window.IterMarkdown.render(chatInput.value)
      : '<p class="preview-empty">Nothing to preview yet.</p>';
    composerPreview.hidden = false;
    chatInput.hidden = true;
  } else {
    composerPreview.hidden = true;
    chatInput.hidden = false;
    chatInput.focus();
  }
  btnPreview.setAttribute('aria-pressed', String(show));
  btnPreview.classList.toggle('active', show);
}
btnPreview.addEventListener('click', () => togglePreview());
composerPreview.addEventListener('click', (event) => {
  if (!event.target.closest('a')) togglePreview(false);
});

chatInput.addEventListener('keydown', (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
    return;
  }
  if (!mod) return;
  const key = e.key.toLowerCase();
  if (key === 'b') { e.preventDefault(); FORMATS.bold(); }
  else if (key === 'i') { e.preventDefault(); FORMATS.italic(); }
  else if (key === 'k') { e.preventDefault(); FORMATS.link(); }
  else if (e.shiftKey && key === 'x') { e.preventDefault(); FORMATS.strike(); }
  else if (e.shiftKey && key === 'c') { e.preventDefault(); FORMATS.code(); }
  else if (e.shiftKey && key === 'p') { e.preventDefault(); togglePreview(); }
});
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'p' && !composerPreview.hidden) {
    e.preventDefault();
    togglePreview(false);
  }
});

// Auto-grow the chat textarea as the user types, up to ~9 rows, so long
// messages stay fully visible and editable instead of scrolling inside a
// fixed-height box. Added 2026-09-14.
const CHAT_INPUT_MAX_ROWS = 9;
function autoGrowChatInput() {
  const cs = window.getComputedStyle(chatInput);
  const lineHeight = parseFloat(cs.lineHeight) || 16;
  const paddingV = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const borderV = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
  const maxHeight = lineHeight * CHAT_INPUT_MAX_ROWS + paddingV + borderV;
  chatInput.style.height = 'auto';
  const needed = chatInput.scrollHeight;
  chatInput.style.height = Math.min(needed, maxHeight) + 'px';
  chatInput.style.overflowY = needed > maxHeight ? 'auto' : 'hidden';
}
chatInput.addEventListener('input', autoGrowChatInput);
autoGrowChatInput();

async function sendChat() {
  if (!composerPreview.hidden) togglePreview(false);
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';
  autoGrowChatInput();
  try {
    const accepted = await window.iterApi.sendChat(text);
    mergeChatMessage(accepted);
  } catch (error) {
    addMessage('sys', `Message was not queued: ${error.message}`);
    chatInput.value = text;
    autoGrowChatInput();
  }
}

// Register the live listener before requesting history. If a message arrives
// between those operations, its stable id makes the subsequent replay a
// harmless dedupe rather than a loss or duplicate.
window.iterApi.onChatIncoming(mergeChatMessage);
let chatHistorySyncInFlight = null;
let chatHistoryFailureShown = false;

function syncChatHistory() {
  if (chatHistorySyncInFlight) return chatHistorySyncInFlight;
  chatHistorySyncInFlight = window.iterApi.chatHistory()
    .then((history) => {
      chatHistoryFailureShown = false;
      mergeChatHistory(history);
    })
    .catch((error) => {
      if (!chatHistoryFailureShown) {
        chatHistoryFailureShown = true;
        addMessage('sys', `Chat history unavailable: ${error.message}`);
      }
    })
    .finally(() => { chatHistorySyncInFlight = null; });
  return chatHistorySyncInFlight;
}

let sidebarStateSyncInFlight = null;
function syncSidebarState() {
  if (sidebarStateSyncInFlight) return sidebarStateSyncInFlight;
  sidebarStateSyncInFlight = Promise.all([
    syncChatHistory(),
    window.iterApi.iterStatus().then((status) => setRunning(status.running, status.stopping)),
    window.iterApi.recentLog().then((lines) => {
      logView.textContent = lines.map((line) => line.endsWith('\n') ? line : line + '\n').join('');
      logView.scrollTop = logView.scrollHeight;
    }),
  ]).finally(() => { sidebarStateSyncInFlight = null; });
  return sidebarStateSyncInFlight;
}

syncSidebarState();
window.addEventListener('focus', syncSidebarState);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') syncSidebarState();
});
window.iterApi.onUiResume(syncSidebarState);
// Electron may suspend a WebContentsView while the Mac is locked without
// producing a useful visibility transition. A bounded, idempotent replay
// closes that gap when timers resume and keeps chat, status, and the activity
// log aligned with main-process authority. The main process also forces a
// compositor invalidation at the operating-system unlock/resume boundary.
setInterval(() => {
  if (document.visibilityState !== 'hidden') syncSidebarState();
}, 2000);

// ---------------------------------------------------------------------
// Iter process controls
// ---------------------------------------------------------------------
function setRunning(running, stopping = false) {
  statusDot.classList.toggle('on', running);
  statusText.textContent = stopping ? 'stopping' : running ? 'running' : 'stopped';
  btnStart.disabled = running || stopping;
  btnStop.disabled = !running || stopping;
}

btnStart.addEventListener('click', async () => {
  btnStart.disabled = true;
  try {
    await saveSettingsFromForm();
    const result = await window.iterApi.startIter();
    if (result && result.error) throw new Error(result.error);
    await syncSidebarState();
    if (!result || !result.cancelled) addMessage('sys', 'Iter starting…');
  } catch (error) {
    addMessage('sys', 'Iter did not start: ' + error.message);
    await syncSidebarState();
  }
});
btnStop.addEventListener('click', async () => {
  btnStop.disabled = true;
  try {
    await window.iterApi.stopIter();
    await syncSidebarState();
    addMessage('sys', 'Iter stopped.');
  } catch (error) {
    addMessage('sys', 'Iter did not stop: ' + error.message);
    await syncSidebarState();
  }
});

window.iterApi.onIterStatus((status) => setRunning(status.running, status.stopping));
// Initial and resume reconciliation is owned by syncSidebarState() above.

window.iterApi.onIterLog((line) => {
  logView.textContent += line.endsWith('\n') ? line : line + '\n';
  logView.scrollTop = logView.scrollHeight;
});
// Initial and resume reconciliation is owned by syncSidebarState() above.

// ---------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------
const providerSel = document.getElementById('provider');
const orEndpoint = document.getElementById('or-endpoint');
const orModel = document.getElementById('or-model');
const orKey = document.getElementById('or-key');
const lmEndpoint = document.getElementById('lm-endpoint');
const lmModel = document.getElementById('lm-model');
const panelOR = document.getElementById('panel-openrouter');
const panelLM = document.getElementById('panel-lmstudio');
const panelOA = document.getElementById('panel-openai');
const oaModel = document.getElementById('oa-model');
const oaKey = document.getElementById('oa-key');
const oaReasoning = document.getElementById('oa-reasoning');
let openaiCatalog = { models: [] };

function paintOpenAIPrice() {
  const rate = openaiCatalog.models.find((model) => model.id === oaModel.value);
  document.getElementById('oa-price').textContent = rate
    ? `USD per 1M tokens: input $${rate.input.toFixed(2)} · cached input $${rate.cachedInput.toFixed(2)} · cache writes $${rate.cacheWrite.toFixed(3)} · output $${rate.output.toFixed(2)}. Reasoning tokens count as output. Standard short-context rates checked ${openaiCatalog.verifiedOn}; rates can change. Example without caching: 30k input + 2k output ≈ $${(rate.input * 0.03 + rate.output * 0.002).toFixed(3)}, excluding surcharges.`
    : 'Select an OpenAI model to see its token prices.';
}

function paintOpenAIUsage(usage) {
  const target = document.getElementById('oa-usage');
  if (!usage || usage.provider !== 'openai') {
    target.textContent = 'No direct OpenAI request recorded yet.';
    return;
  }
  const tokens = usage.usage || {};
  const cost = Number.isFinite(usage.estimated_usd) ? `$${usage.estimated_usd.toFixed(5)}` : 'unavailable';
  target.textContent = `Last OpenAI request: ${usage.model}, ${new Date(usage.at * 1000).toLocaleString()}, ${usage.seconds}s. Input ${tokens.input_tokens ?? '?'} · output ${tokens.output_tokens ?? '?'} (reasoning ${(tokens.output_tokens_details || {}).reasoning_tokens ?? '?'}). Estimated text-token cost ${cost}. ${usage.note || ''} This is one request, not your account balance or whole-task cost.`;
}
oaModel.addEventListener('change', paintOpenAIPrice);
document.getElementById('btn-oa-usage').addEventListener('click', async () => {
  paintOpenAIUsage((await window.iterApi.loadSettings()).lastModelUsage);
});

function syncProviderPanels() {
  panelOR.style.display = providerSel.value === 'openrouter' ? 'flex' : 'none';
  panelLM.style.display = providerSel.value === 'lmstudio' ? 'flex' : 'none';
  panelOA.style.display = providerSel.value === 'openai' ? 'flex' : 'none';
}
providerSel.addEventListener('change', syncProviderPanels);

async function saveSettingsFromForm() {
  // Merge onto the current settings rather than replacing the whole file --
  // saveSettings() is a straight overwrite (see main.js), so building a
  // fresh object with only these 3 keys would silently wipe sidebarWidth
  // and the dock tab order/last-open state (added 2026-09-17) every time
  // this runs, which includes every "Start" click, not just "Save settings".
  const current = await window.iterApi.loadSettings();
  const settings = {
    ...current,
    provider: providerSel.value,
    openrouter: { ...current.openrouter, endpoint: orEndpoint.value, model: orModel.value, apiKey: orKey.value },
    openai: { ...current.openai, model: oaModel.value, apiKey: oaKey.value.trim(), reasoning: oaReasoning.value },
    lmstudio: { ...current.lmstudio, endpoint: lmEndpoint.value, model: lmModel.value },
  };
  await window.iterApi.saveSettings(settings);
}
document.getElementById('btn-save-settings').addEventListener('click', () => {
  saveSettingsFromForm().then(() => addMessage('sys', 'Settings saved. Restart Iter (Stop, then Start) for changes to take effect.'));
});

window.iterApi.loadSettings().then((settings) => {
  providerSel.value = settings.provider || 'openrouter';
  orEndpoint.value = settings.openrouter.endpoint;
  orModel.value = settings.openrouter.model;
  orKey.value = settings.openrouter.apiKey || '';
  openaiCatalog = settings.openaiCatalog || { models: [] };
  oaModel.replaceChildren(...openaiCatalog.models.map((model) => {
    const option = document.createElement('option');
    option.value = model.id;
    option.textContent = model.label;
    return option;
  }));
  oaModel.value = (settings.openai || {}).model || 'gpt-6-sol';
  oaKey.value = (settings.openai || {}).apiKey || '';
  oaReasoning.value = (settings.openai || {}).reasoning || 'low';
  paintOpenAIPrice();
  paintOpenAIUsage(settings.lastModelUsage);
  lmEndpoint.value = settings.lmstudio.endpoint;
  lmModel.value = settings.lmstudio.model;
  syncProviderPanels();
});

// ---------------------------------------------------------------------
// Permissions -- Camera & Microphone
// ---------------------------------------------------------------------
const PERM_LABELS = {
  'not-determined': 'not requested yet',
  granted: 'granted',
  denied: 'denied',
  restricted: 'restricted (managed by an org policy)',
  unknown: 'unknown',
};

function paintPermStatus(el, status) {
  el.textContent = PERM_LABELS[status] || status;
  el.style.color = status === 'granted' ? '#4caf7d' : status === 'denied' ? '#ff6b6b' : 'var(--muted)';
}

function refreshPermissions() {
  window.iterApi.permissionsStatus().then((s) => {
    paintPermStatus(document.getElementById('perm-camera-status'), s.camera);
    paintPermStatus(document.getElementById('perm-mic-status'), s.microphone);
  });
}
refreshPermissions();

document.getElementById('btn-perm-camera-request').addEventListener('click', () => {
  window.iterApi.requestPermission('camera').then(refreshPermissions);
});
document.getElementById('btn-perm-mic-request').addEventListener('click', () => {
  window.iterApi.requestPermission('microphone').then(refreshPermissions);
});
document.getElementById('btn-perm-camera-settings').addEventListener('click', () => {
  window.iterApi.openPermissionSettings('camera');
});
document.getElementById('btn-perm-mic-settings').addEventListener('click', () => {
  window.iterApi.openPermissionSettings('microphone');
});

// ---------------------------------------------------------------------
// State: Export / Import / Reset
// ---------------------------------------------------------------------
const stateStatus = document.getElementById('state-mgmt-status');

document.getElementById('btn-export-state').addEventListener('click', async () => {
  stateStatus.textContent = 'Exporting…';
  try {
    const result = await window.iterApi.exportState();
    if (result.canceled) { stateStatus.textContent = ''; return; }
    const missing = result.missing || [];
    stateStatus.textContent = `Exported ${result.itemCount} item(s) to ` + result.exported + (missing.length ? ` (${missing.length} not found, see log)` : '');
    addMessage('sys', 'State exported to ' + result.exported + ` -- ${result.itemCount} item(s) included` + (missing.length ? `; not found on disk so skipped: ${missing.join(', ')}` : ''));
  } catch (e) {
    stateStatus.textContent = 'Export failed: ' + e.message;
  }
});

document.getElementById('btn-import-state').addEventListener('click', async () => {
  const ok = confirm('Import will replace Iter\'s current memory, vector store, and knowledge files with the contents of the zip you pick. Continue?');
  if (!ok) return;
  stateStatus.textContent = 'Importing…';
  try {
    const result = await window.iterApi.importState();
    if (result && result.imported) await replaceChatFromHistory();
    if (result.canceled) { stateStatus.textContent = ''; return; }
    const notFound = result.notFoundInZip || [];
    stateStatus.textContent = `Imported ${result.itemCount} item(s) from ` + result.imported + (notFound.length ? ` (${notFound.length} not in this zip)` : '');
    addMessage('sys', 'State imported from ' + result.imported + ` -- ${result.itemCount} item(s) restored` + (notFound.length ? `; not present in this zip: ${notFound.join(', ')}` : '') + (result.restarted ? ' (Iter restarted)' : ''));
    setRunning(result.restarted);
  } catch (e) {
    stateStatus.textContent = 'Import failed: ' + e.message;
  }
});

document.getElementById('btn-restore-state').addEventListener('click', async () => {
  // No confirm() here -- restoreState() shows its own native picker over the
  // rolling auto-backups (main.js), and cancelling that picker returns
  // { canceled: true } same as Export/Import's own dialogs.
  stateStatus.textContent = 'Restoring…';
  try {
    const result = await window.iterApi.restoreState();
    if (result && result.imported) await replaceChatFromHistory();
    if (result.canceled) { stateStatus.textContent = ''; return; }
    if (result.error) { stateStatus.textContent = 'Restore failed: ' + result.error; return; }
    const notFound = result.notFoundInZip || [];
    stateStatus.textContent = `Restored ${result.itemCount} item(s) from ` + result.restoredFrom + (notFound.length ? ` (${notFound.length} not in this backup)` : '');
    addMessage('sys', 'State restored from auto-backup ' + result.restoredFrom + ` -- ${result.itemCount} item(s) restored` + (notFound.length ? `; not present in this backup: ${notFound.join(', ')}` : '') + (result.restarted ? ' (Iter restarted)' : ''));
    setRunning(result.restarted);
  } catch (e) {
    stateStatus.textContent = 'Restore failed: ' + e.message;
  }
});

document.getElementById('btn-reset-state').addEventListener('click', async () => {
  const ok = confirm('Factory Reset: Iter forgets everything it has accumulated -- memory, conversation and chat history, beliefs, the PWQ board and saved outputs -- and starts fresh.\n\nKept: your code, settings and API keys, tabs, the apps you built, CRM contacts and uploaded files.\n\nA backup of everything Reset removes is saved first; you can return to it with Restore.\n\nContinue?');
  if (!ok) return;
  stateStatus.textContent = 'Saving a backup, then resetting…';
  try {
    const result = await window.iterApi.resetState();
    await replaceChatFromHistory();
    const saved = result && result.backup ? result.backup.split('/').pop() : 'a backup';
    stateStatus.textContent = 'State reset. Backup: ' + saved;
    addMessage('sys', 'State reset (backup saved as ' + saved + ', available under Restore).'
      + (result && result.restarted ? ' Iter restarted with a fresh state.' : ' Press Start to begin fresh.'));
    setRunning(!!(result && result.restarted));
  } catch (e) {
    stateStatus.textContent = 'Reset failed: ' + e.message;
  }
});

// ---------------------------------------------------------------------
// Tab Groups -- save the currently open tabs under a name, then later
// open/switch-to/close/delete that saved group. Added 2026-09-14.
// ---------------------------------------------------------------------
const tabGroupsList = document.getElementById('tab-groups-list');
const tabGroupNameInput = document.getElementById('tab-group-name');

function renderTabGroups(groups) {
  tabGroupsList.innerHTML = '';
  if (!groups.length) {
    tabGroupsList.innerHTML = '<div style="font-size:10px;color:var(--muted)">No saved groups yet.</div>';
    return;
  }
  for (const g of groups) {
    const row = document.createElement('div');
    row.className = 'tab-group-item';
    row.innerHTML = `<span class="name" title="${escapeHtml(g.name)}">${escapeHtml(g.name)}</span><span class="count">${g.tabs.length} tab${g.tabs.length === 1 ? '' : 's'}</span><span class="actions"><button data-act="resave" title="Replace this group's tabs with your currently open tabs">Resave</button><button data-act="open">Open</button><button data-act="switch">Switch</button><button data-act="close">Close</button><button data-act="delete">Delete</button></span>`;
    // Resave -- re-snapshots current tabs into THIS group by id, added
    // 2026-09-17 so updating a group (e.g. after removing tabs you no
    // longer want in it) never depends on retyping its exact name.
    row.querySelector('[data-act="resave"]').addEventListener('click', async () => {
      const ok = confirm(`Replace "${g.name}"'s saved tabs with your currently open tabs?`);
      if (!ok) return;
      const updated = await window.iterApi.resaveTabGroup(g.id);
      renderTabGroups(updated);
    });
    row.querySelector('[data-act="open"]').addEventListener('click', async () => {
      await window.iterApi.openTabGroup(g.id);
    });
    row.querySelector('[data-act="switch"]').addEventListener('click', async () => {
      const ok = confirm(`Switch to "${g.name}"? This closes your current unpinned/unlocked tabs first.`);
      if (!ok) return;
      await window.iterApi.switchToTabGroup(g.id);
    });
    row.querySelector('[data-act="close"]').addEventListener('click', async () => {
      await window.iterApi.closeTabGroup(g.id);
    });
    row.querySelector('[data-act="delete"]').addEventListener('click', async () => {
      const ok = confirm(`Delete the saved group "${g.name}"? This does not close any open tabs.`);
      if (!ok) return;
      const updated = await window.iterApi.deleteTabGroup(g.id);
      renderTabGroups(updated);
    });
    tabGroupsList.appendChild(row);
  }
}

document.getElementById('btn-save-tab-group').addEventListener('click', async () => {
  const name = tabGroupNameInput.value.trim();
  if (!name) return;
  const updated = await window.iterApi.saveTabGroup(name);
  tabGroupNameInput.value = '';
  renderTabGroups(updated);
});

window.iterApi.listTabGroups().then(renderTabGroups);
document.getElementById('tab-groups').addEventListener('panelshow', () => {
  window.iterApi.listTabGroups().then(renderTabGroups);
});

// ---------------------------------------------------------------------
// Recently Closed -- browsable panel over the same closed_tabs.json
// history already used by the History menu / tab right-click "Reopen
// Last Closed Tab". Added 2026-09-17 so an accidentally-closed tab can be
// recovered from inside the app instead of only via the native menu bar.
// ---------------------------------------------------------------------
const closedTabsList = document.getElementById('closed-tabs-list');

function renderClosedTabs(list) {
  closedTabsList.innerHTML = '';
  if (!list.length) {
    closedTabsList.innerHTML = '<div style="font-size:10px;color:var(--muted)">No recently closed tabs.</div>';
    return;
  }
  list.forEach((entry, i) => {
    const row = document.createElement('div');
    row.className = 'closed-tab-item';
    const label = entry.title || entry.url;
    const when = entry.closedAt ? new Date(entry.closedAt).toLocaleString() : '';
    row.innerHTML = `<span class="title" title="${escapeHtml(entry.url)}">${escapeHtml(label)}</span><span class="closed-at">${escapeHtml(when)}</span><button data-act="reopen">Reopen</button>`;
    row.querySelector('[data-act="reopen"]').addEventListener('click', async () => {
      const updated = await window.iterApi.reopenClosedTab(i);
      renderClosedTabs(updated);
    });
    closedTabsList.appendChild(row);
  });
}

window.iterApi.listClosedTabs().then(renderClosedTabs);
document.getElementById('closed-tabs').addEventListener('panelshow', () => {
  window.iterApi.listClosedTabs().then(renderClosedTabs);
});

// ---------------------------------------------------------------------
// Sidebar resize
// ---------------------------------------------------------------------
const appShell = document.getElementById('app-shell');
const resizeHandle = document.getElementById('resize-handle');
const dragCatcher = document.getElementById('drag-catcher');
let resizing = false;
let pendingWidth = null;

resizeHandle.addEventListener('mousedown', async (e) => {
  e.preventDefault();
  resizing = true;
  dragCatcher.classList.add('active');
  await window.iterApi.resizeSidebarStart();
  appShell.style.width = appShell.getBoundingClientRect().width + 'px';
});

dragCatcher.addEventListener('mousemove', (e) => {
  if (!resizing) return;
  pendingWidth = e.clientX;
  requestAnimationFrame(flushResizeMove);
});

function flushResizeMove() {
  if (!resizing || pendingWidth === null) return;
  const width = pendingWidth;
  pendingWidth = null;
  window.iterApi.resizeSidebarMove(width).then((res) => {
    if (res && res.width) appShell.style.width = res.width + 'px';
  });
}

window.addEventListener('mouseup', async () => {
  if (!resizing) return;
  resizing = false;
  dragCatcher.classList.remove('active');
  await window.iterApi.resizeSidebarEnd();
  appShell.style.width = ''; // back to the CSS default (100%), now matching the shrunk native view
});

// ---------------------------------------------------------------------
// Terminal & Files
// ---------------------------------------------------------------------
const tfBreadcrumb = document.getElementById('tf-breadcrumb');
const tfTree = document.getElementById('tf-tree');
const tfUp = document.getElementById('tf-up');
const tfRefresh = document.getElementById('tf-refresh');
const tfCurrentFile = document.getElementById('tf-current-file');
const tfEditor = document.getElementById('tf-editor');
const tfSave = document.getElementById('tf-save');
const tfTermOutput = document.getElementById('tf-term-output');
const tfTermInput = document.getElementById('tf-term-input');
const tfTermCwd = document.getElementById('tf-term-cwd');
const tfTermInterrupt = document.getElementById('tf-term-interrupt');
const tfTermStop = document.getElementById('tf-term-stop');
const termfilesDetails = document.getElementById('termfiles');

let tfCurrentDir = '.';
let tfOpenFile = null;
let tfDirty = false;
let termStarted = false;

async function tfLoadDir(relPath) {
  try {
    const res = await window.iterApi.fsList(relPath);
    tfCurrentDir = res.path;
    tfBreadcrumb.textContent = '/' + (tfCurrentDir === '.' ? '' : tfCurrentDir);
    tfTree.innerHTML = '';
    for (const item of res.items) {
      const row = document.createElement('div');
      row.className = 'tf-entry ' + (item.isDir ? 'dir' : 'file');
      row.textContent = item.name;
      const childRel = tfCurrentDir === '.' ? item.name : tfCurrentDir + '/' + item.name;
      row.addEventListener('click', () => {
        if (item.isDir) tfLoadDir(childRel);
        else tfOpenFileAt(childRel);
      });
      tfTree.appendChild(row);
    }
  } catch (e) {
    tfTree.innerHTML = '';
    const err = document.createElement('div');
    err.className = 'tf-muted';
    err.textContent = 'Error: ' + e.message;
    tfTree.appendChild(err);
  }
}

async function tfOpenFileAt(relPath) {
  if (tfDirty && !confirm('Discard unsaved changes to ' + tfOpenFile + '?')) return;
  try {
    const res = await window.iterApi.fsRead(relPath);
    if (res.tooLarge) {
      tfEditor.value = '';
      tfEditor.disabled = true;
      tfSave.disabled = true;
      tfCurrentFile.textContent = relPath + ' (too large to edit — ' + res.size + ' bytes)';
      tfOpenFile = null;
      return;
    }
    if (res.binary) {
      tfEditor.value = '';
      tfEditor.disabled = true;
      tfSave.disabled = true;
      tfCurrentFile.textContent = relPath + ' (binary file, not shown)';
      tfOpenFile = null;
      return;
    }
    tfEditor.value = res.content;
    tfEditor.disabled = false;
    tfSave.disabled = false;
    tfCurrentFile.textContent = relPath;
    tfOpenFile = relPath;
    tfDirty = false;
  } catch (e) {
    tfCurrentFile.textContent = 'Error: ' + e.message;
  }
}

tfEditor.addEventListener('input', () => { tfDirty = true; });

tfSave.addEventListener('click', async () => {
  if (!tfOpenFile) return;
  try {
    await window.iterApi.fsWrite(tfOpenFile, tfEditor.value);
    tfDirty = false;
    tfCurrentFile.textContent = tfOpenFile + ' (saved)';
    setTimeout(() => { if (!tfDirty && tfOpenFile) tfCurrentFile.textContent = tfOpenFile; }, 1500);
  } catch (e) {
    tfCurrentFile.textContent = 'Save failed: ' + e.message;
  }
});

tfUp.addEventListener('click', () => {
  if (tfCurrentDir === '.' || tfCurrentDir === '') return;
  const parts = tfCurrentDir.split('/');
  parts.pop();
  tfLoadDir(parts.length ? parts.join('/') : '.');
});
tfRefresh.addEventListener('click', () => tfLoadDir(tfCurrentDir));

function tfAppendTerm(text) {
  tfTermOutput.textContent += text;
  tfTermOutput.scrollTop = tfTermOutput.scrollHeight;
}

window.iterApi.onTerminalData((chunk) => tfAppendTerm(chunk));
window.iterApi.onTerminalDone((info) => {
  if (info.cwd) tfTermCwd.textContent = info.cwd;
  tfAppendTerm('\n$ ');
});

tfTermInput.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const cmd = tfTermInput.value;
  tfTermInput.value = '';
  if (!termStarted) { await window.iterApi.terminalStart(); termStarted = true; }
  tfAppendTerm(cmd + '\n');
  await window.iterApi.terminalRun(cmd);
});

tfTermInterrupt.addEventListener('click', () => window.iterApi.terminalInterrupt());
tfTermStop.addEventListener('click', async () => {
  await window.iterApi.terminalStop();
  termStarted = false;
  tfAppendTerm('\n[terminal stopped]\n');
});

// Lazily start the shell and load the file tree the first time the panel
// is opened, rather than at page load (keeps startup light).
let termfilesInitialized = false;
termfilesDetails.addEventListener('panelshow', async () => {
  if (termfilesInitialized) return;
  termfilesInitialized = true;
  tfLoadDir('.');
  await window.iterApi.terminalStart();
  termStarted = true;
  tfAppendTerm('$ ');
});

// ---------------------------------------------------------------------
// Bottom tab dock -- replaced the old stack of 7 always-visible <details>
// accordion panels on 2026-09-17. One row of tab handles pinned to the
// bottom edge (modeled on VS Code's bottom panel tabs); at most one
// drawer open above the row at a time. Order and last-open tab persist
// to settings.json (local to this Mac -- see saveDockState below).
// ---------------------------------------------------------------------
const DOCK_PANEL_INFO = {
  'settings': { label: 'Settings', desc: 'OpenRouter, direct OpenAI GPT, or local LM Studio; models, API keys and OpenAI token costs.' },
  'state-mgmt': { label: 'State', desc: 'Export, import, or reset Iter\u2019s accumulated memory and knowledge files.' },
  'tab-groups': { label: 'Groups', desc: 'Tab Groups -- save your open tabs as a named group; reopen, switch to, or close it later.' },
  'closed-tabs': { label: 'Closed', desc: 'Recently Closed -- the last 20 tabs you closed, most recent first. Reopen any of them.' },
  'permissions': { label: 'Perms', desc: 'Permissions -- camera and microphone access for Iter Browser.' },
  'termfiles': { label: 'Terminal', desc: 'Terminal & Files -- browse/edit files under iter/ and run shell commands.' },
  'activity': { label: 'Activity', desc: 'Iter\u2019s process output log.' },
};
const DOCK_DEFAULT_ORDER = ['settings', 'state-mgmt', 'tab-groups', 'closed-tabs', 'permissions', 'termfiles', 'activity'];

const dockContent = document.getElementById('dock-content');
const dockTabsEl = document.getElementById('dock-tabs');
const dockPanels = {};
document.querySelectorAll('.dock-panel').forEach((p) => { dockPanels[p.id] = p; });

let activeDockPanel = null;
let dockTooltipTimer = null;
let dockTooltipEl = null;

function hideDockTooltip() {
  clearTimeout(dockTooltipTimer);
  if (dockTooltipEl) { dockTooltipEl.remove(); dockTooltipEl = null; }
}

function showDockTooltip(btn, panelId) {
  hideDockTooltip();
  dockTooltipTimer = setTimeout(() => {
    const info = DOCK_PANEL_INFO[panelId];
    if (!info) return;
    const rect = btn.getBoundingClientRect();
    dockTooltipEl = document.createElement('div');
    dockTooltipEl.className = 'dock-tooltip';
    dockTooltipEl.innerHTML = `<strong>${escapeHtml(info.label)}</strong><br>${escapeHtml(info.desc)}`;
    document.body.appendChild(dockTooltipEl);
    const tw = dockTooltipEl.getBoundingClientRect().width;
    let left = rect.left;
    if (left + tw > window.innerWidth - 6) left = Math.max(6, window.innerWidth - tw - 6);
    dockTooltipEl.style.left = left + 'px';
    dockTooltipEl.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
  }, 450);
}

function setActiveDockPanel(id, { persist = true } = {}) {
  document.querySelectorAll('.dock-tab').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.panel === id);
  });
  Object.values(dockPanels).forEach((p) => { p.hidden = true; });
  if (id && dockPanels[id]) {
    dockPanels[id].hidden = false;
    dockContent.hidden = false;
    dockPanels[id].dispatchEvent(new CustomEvent('panelshow'));
  } else {
    id = null;
    dockContent.hidden = true;
  }
  activeDockPanel = id;
  if (persist) saveDockState();
}

function currentDockOrder() {
  return Array.from(dockTabsEl.querySelectorAll('.dock-tab')).map((b) => b.dataset.panel);
}

async function saveDockState() {
  const current = await window.iterApi.loadSettings();
  await window.iterApi.saveSettings({ ...current, dockOrder: currentDockOrder(), dockLastOpen: activeDockPanel });
}

let dockDragSrc = null;

function buildDockTabs(order) {
  dockTabsEl.innerHTML = '';
  order.forEach((id) => {
    const info = DOCK_PANEL_INFO[id];
    if (!info || !dockPanels[id]) return;
    const btn = document.createElement('button');
    btn.className = 'dock-tab';
    btn.type = 'button';
    btn.dataset.panel = id;
    btn.draggable = true;
    btn.textContent = info.label;
    btn.addEventListener('click', () => {
      setActiveDockPanel(activeDockPanel === id ? null : id);
    });
    btn.addEventListener('mouseenter', () => showDockTooltip(btn, id));
    btn.addEventListener('mouseleave', hideDockTooltip);
    btn.addEventListener('dragstart', (e) => {
      dockDragSrc = id;
      e.dataTransfer.effectAllowed = 'move';
      hideDockTooltip();
    });
    btn.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (dockDragSrc && dockDragSrc !== id) btn.classList.add('drag-over');
    });
    btn.addEventListener('dragleave', () => btn.classList.remove('drag-over'));
    btn.addEventListener('drop', (e) => {
      e.preventDefault();
      btn.classList.remove('drag-over');
      if (!dockDragSrc || dockDragSrc === id) return;
      const srcBtn = dockTabsEl.querySelector(`[data-panel="${dockDragSrc}"]`);
      if (!srcBtn) return;
      const rect = btn.getBoundingClientRect();
      const before = (e.clientX - rect.left) < rect.width / 2;
      dockTabsEl.insertBefore(srcBtn, before ? btn : btn.nextSibling);
      dockDragSrc = null;
      saveDockState();
    });
    btn.addEventListener('dragend', () => { dockDragSrc = null; });
    dockTabsEl.appendChild(btn);
  });
}

window.iterApi.loadSettings().then((settings) => {
  const savedOrder = Array.isArray(settings.dockOrder) ? settings.dockOrder : [];
  const known = new Set(DOCK_DEFAULT_ORDER);
  const order = savedOrder.filter((id) => known.has(id));
  for (const id of DOCK_DEFAULT_ORDER) if (!order.includes(id)) order.push(id); // forward-compat: any new panel lands at the end
  buildDockTabs(order);
  if (settings.dockLastOpen && dockPanels[settings.dockLastOpen]) {
    setActiveDockPanel(settings.dockLastOpen, { persist: false });
  }
});
