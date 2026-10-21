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

// ---- Interactive cards (docs/milestones/M6_soul_base.md section A) ----
// Iter offers; the person decides. A click sends exactly one choice and
// locks the card in place (no re-render, so nothing flickers or re-enables).
const localCardPicks = new Map();

function lockCard(cardEl, pick) {
  cardEl.classList.add(pick === 'dismiss' ? 'dismissed' : 'answered');
  for (const button of cardEl.querySelectorAll('button.choice, button.dismiss')) button.disabled = true;
  const picked = pick && cardEl.querySelector(`button.choice[data-choice="${CSS.escape(pick)}"]`);
  if (picked) picked.classList.add('picked');
}

function choose(cardEl, card, pick, label) {
  if (localCardPicks.has(card.id) || cardEl.classList.contains('answered') || cardEl.classList.contains('dismissed')) return;
  localCardPicks.set(card.id, pick);
  lockCard(cardEl, pick);
  Promise.resolve(window.iterApi.sendChoice(card.id, pick, label)).catch((error) => {
    // The choice did not reach Iter: unlock so the person can try again.
    localCardPicks.delete(card.id);
    cardEl.classList.remove('answered', 'dismissed');
    for (const button of cardEl.querySelectorAll('button')) { button.disabled = false; button.classList.remove('picked'); }
    addMessage('sys', 'Could not send your choice: ' + (error && error.message ? error.message : error));
  });
}

function renderCard(card, picks) {
  const cardEl = document.createElement('div');
  cardEl.className = 'card card-' + card.kind;
  cardEl.dataset.card = card.id;
  const head = document.createElement('div');
  head.className = 'card-head';
  const title = document.createElement('div');
  title.className = 'card-title';
  title.textContent = card.title;
  const dismiss = document.createElement('button');
  dismiss.type = 'button';
  dismiss.className = 'dismiss';
  dismiss.title = 'Dismiss';
  dismiss.setAttribute('aria-label', 'Dismiss');
  dismiss.textContent = '×';
  dismiss.addEventListener('click', () => choose(cardEl, card, 'dismiss', ''));
  head.append(title, dismiss);
  cardEl.appendChild(head);
  if (card.body) {
    const body = document.createElement('div');
    body.className = 'card-body markdown';
    body.innerHTML = window.IterMarkdown.render(card.body);
    cardEl.appendChild(body);
  }
  const choices = document.createElement('div');
  choices.className = 'card-choices';
  for (const choice of card.choices || []) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'choice';
    button.dataset.choice = choice.id;
    button.textContent = choice.label;
    if (choice.hint) button.title = choice.hint;
    button.addEventListener('click', () => choose(cardEl, card, choice.id, choice.label));
    choices.appendChild(button);
  }
  cardEl.appendChild(choices);
  if (Array.isArray(card.links) && card.links.length) {
    const links = document.createElement('div');
    links.className = 'card-links';
    for (const link of card.links) {
      const safe = window.IterMarkdown.safeHref(link.url);
      if (!safe) continue;
      const anchor = document.createElement('a');
      anchor.href = safe;
      anchor.textContent = link.label;
      anchor.rel = 'noopener noreferrer';
      links.appendChild(anchor);
    }
    cardEl.appendChild(links);
  }
  const pick = picks.get(card.id);
  if (pick) lockCard(cardEl, pick);
  else if (card.expires_at && Number(card.expires_at) < Date.now()) {
    cardEl.classList.add('expired');
    for (const button of cardEl.querySelectorAll('button')) button.disabled = true;
  }
  return cardEl;
}

function renderChoiceNote(message) {
  const note = document.createElement('div');
  note.className = 'body choice-note';
  const label = message.content.replace(/^\[choice [^\]]*\]\s*/, '');
  note.textContent = message.choice.pick === 'dismiss' ? 'Dismissed a card' : 'Chose: ' + (label || message.choice.pick);
  return note;
}

function renderChatMessages() {
  const stickToBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 40;
  chat.textContent = '';
  const ordered = Array.from(chatMessages.values()).sort((left, right) => {
    const timeDifference = Number(left.at || 0) - Number(right.at || 0);
    return timeDifference || String(left.id).localeCompare(String(right.id));
  });
  // A card shows as answered once the journal holds the person's choice for it
  // (or the click is still on its way: localCardPicks).
  const picks = new Map(localCardPicks);
  for (const message of ordered) {
    if (message.choice && message.choice.card) picks.set(message.choice.card, message.choice.pick);
  }
  let previous = null;
  for (const message of ordered) {
    const row = document.createElement('div');
    row.className = 'msg row ' + message.role;
    if (message.felt === true && message.role === 'iter') row.classList.add('felt');
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
    if (message.felt === true && message.role === 'iter') {
      // A felt note (M7-B2): Iter's own voice, nothing to answer.
      const mark = document.createElement('span');
      mark.className = 'felt-mark';
      mark.setAttribute('aria-hidden', 'true');
      mark.textContent = '✦';
      const body = document.createElement('div');
      body.className = 'body markdown';
      body.innerHTML = window.IterMarkdown.render(message.content);
      row.append(mark, body);
    } else if (message.margin && message.role === 'user') {
      // A request from inside an app tab (M8-D3): where it came from, then what was asked.
      const note = document.createElement('div');
      note.className = 'margin-note';
      const selector = message.margin.element && message.margin.element.selector;
      note.textContent = 'from ' + message.margin.app + (selector ? ' · ' + selector : '');
      const body = document.createElement('div');
      body.className = 'body';
      const text = String(message.content || '').replace(/^\[margin [^\]]*\]\s*/, '');
      if (text) body.textContent = text;
      else {
        const em = document.createElement('em');
        em.textContent = 'jam on this';
        body.appendChild(em);
      }
      row.append(note, body);
    } else if (message.card) {
      row.appendChild(renderCard(message.card, picks));
    } else if (message.choice) {
      row.appendChild(renderChoiceNote(message));
    } else {
      const body = document.createElement('div');
      body.className = 'body' + (message.role === 'sys' ? '' : ' markdown');
      if (message.role === 'sys') body.textContent = message.content;
      else body.innerHTML = window.IterMarkdown.render(message.content);
      row.appendChild(body);
    }
    chat.appendChild(row);
    previous = message;
  }
  if (stickToBottom) chat.scrollTop = chat.scrollHeight;
}

// A link anywhere in the sidebar (chat, composer preview, panels) opens as a
// browser tab; the sidebar page itself never navigates. main.js enforces the
// same rule at the process level in case a click slips past this handler.
document.addEventListener('click', (event) => {
  const anchor = event.target.closest('a[href]');
  if (!anchor) return;
  event.preventDefault();
  const href = window.IterMarkdown.safeHref(anchor.getAttribute('href'));
  if (href && /^https?:/i.test(href)) window.iterApi.newTab(href);
}, true);

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
  if (event.target.closest('a')) return; // the link opened as a tab; keep previewing
  togglePreview(false);
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
// M16-B3: one panel for every provider. The main process keeps the keys; this page only knows hasKey.
const providerSel = document.getElementById('provider');
const settingEndpoint = document.getElementById('settings-endpoint');
const modelSelect = document.getElementById('settings-model-select');
const settingModel = document.getElementById('settings-model');
const settingKey = document.getElementById('settings-key');
const oaReasoning = document.getElementById('oa-reasoning');
const testResult = document.getElementById('settings-test-result');
let openaiCatalog = { models: [] };
let panel = { provider: 'openrouter', providers: {} };
const drafts = {}; // provider -> what the form holds for it (switching providers loses nothing)

function route(provider) {
  if (!drafts[provider]) {
    const p = panel.providers[provider] || {};
    drafts[provider] = { endpoint: p.endpoint || '', model: p.model || '', reasoning: p.reasoning || 'low', key: '',
      models: (p.models || []).slice(), pricing: p.pricing || null };
  }
  return drafts[provider];
}

function chosenModel() {
  return settingModel.value.trim() || modelSelect.value;
}

function paintModelPrice() {
  const provider = providerSel.value;
  const d = route(provider);
  const target = document.getElementById('settings-model-price');
  const price = d.pricing && d.pricing[chosenModel()];
  target.textContent = price ? `USD per 1M tokens: input $${price.input} · output $${price.output} (from the provider's model list).` : '';
  if (provider === 'openai') paintOpenAIPrice();
}

function paintOpenAIPrice() {
  const rate = openaiCatalog.models.find((model) => model.id === chosenModel());
  document.getElementById('oa-price').textContent = providerSel.value !== 'openai' ? '' : rate
    ? `USD per 1M tokens: input $${rate.input.toFixed(2)} · cached input $${rate.cachedInput.toFixed(2)} · cache writes $${rate.cacheWrite.toFixed(3)} · output $${rate.output.toFixed(2)}. Reasoning tokens count as output. Standard short-context rates checked ${openaiCatalog.verifiedOn}; rates can change. Example without caching: 30k input + 2k output ≈ $${(rate.input * 0.03 + rate.output * 0.002).toFixed(3)}, excluding surcharges.`
    : 'Choose one of the OpenAI models IterBrow knows the prices of.';
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
document.getElementById('btn-oa-usage').addEventListener('click', async () => {
  paintOpenAIUsage((await window.iterApi.loadSettings()).lastModelUsage);
});

function fillModelList(models, selected) {
  const options = [new Option(models.length ? '— choose a model —' : '— Fetch models, or type one below —', '')];
  for (const id of models) options.push(new Option(id, id));
  modelSelect.replaceChildren(...options);
  modelSelect.value = models.includes(selected) ? selected : '';
}

function keepDraft() {
  const d = route(providerSel.dataset.shown || providerSel.value);
  d.endpoint = settingEndpoint.value.trim();
  d.model = chosenModel();
  d.reasoning = oaReasoning.value;
  d.key = settingKey.value;
}

function showProvider() {
  const provider = providerSel.value;
  const p = panel.providers[provider] || {};
  const d = route(provider);
  providerSel.dataset.shown = provider;
  document.getElementById('settings-note').textContent = p.note || '';
  settingEndpoint.value = d.endpoint;
  settingEndpoint.readOnly = provider === 'openai';
  const known = provider === 'openai' ? openaiCatalog.models.map((m) => m.id) : d.models;
  fillModelList(known, d.model);
  settingModel.value = known.includes(d.model) ? '' : d.model;
  oaReasoning.value = d.reasoning || 'low';
  document.getElementById('settings-reasoning-field').style.display = provider === 'openai' ? '' : 'none';
  document.getElementById('settings-openai-usage').style.display = provider === 'openai' ? '' : 'none';
  document.getElementById('settings-key-field').style.display = p.needsKey || provider === 'custom' ? '' : 'none';
  settingKey.value = d.key;
  settingKey.placeholder = p.hasKey ? 'stored — leave empty to keep it' : (p.needsKey ? 'paste your API key' : 'only if your server asks for one');
  testResult.textContent = '';
  paintModelPrice();
}

providerSel.addEventListener('change', () => { keepDraft(); showProvider(); });
// Click a model in the list and it is the model (the typed field is cleared so the click wins).
modelSelect.addEventListener('change', () => { settingModel.value = ''; route(providerSel.value).model = modelSelect.value; paintModelPrice(); });
settingModel.addEventListener('input', paintModelPrice);

function formRoute() {
  keepDraft();
  const provider = providerSel.value;
  const d = route(provider);
  return { provider, endpoint: d.endpoint, model: d.model, reasoning: provider === 'openai' ? d.reasoning : undefined, key: d.key.trim() };
}

document.getElementById('btn-settings-fetch').addEventListener('click', async () => {
  const r = formRoute();
  testResult.textContent = 'Asking for the model list…';
  const result = await window.iterApi.fetchModels({ provider: r.provider, endpoint: r.endpoint, key: r.key });
  if (!result.ok) { testResult.textContent = 'Fetch models: ' + result.error; return; }
  const d = route(r.provider);
  d.models = result.models;
  if (result.pricing) d.pricing = result.pricing;
  fillModelList(result.models, d.model);
  testResult.textContent = `${result.models.length} models listed${result.pricing ? ' (with prices)' : ''} — click one, then Test connection.`;
});

document.getElementById('btn-settings-test').addEventListener('click', async () => {
  const r = formRoute();
  testResult.textContent = r.model ? `Testing ${r.model}…` : 'Testing the model list…';
  const result = await window.iterApi.testConnection(r);
  testResult.textContent = result.text;
  testResult.style.color = result.ok ? '#4caf7d' : '#ff6b6b';
});

function panelChange() {
  const r = formRoute();
  const entry = { endpoint: r.endpoint, model: r.model, apiKey: r.key };
  if (r.provider === 'openai') entry.reasoning = r.reasoning;
  const d = route(r.provider);
  if (d.models.length) entry.models = d.models;
  if (d.pricing) entry.pricing = d.pricing;
  return { provider: r.provider, [r.provider]: entry };
}

document.getElementById('btn-settings-apply').addEventListener('click', async () => {
  const result = await window.iterApi.saveSettings({ ...panelChange(), apply: true });
  route(providerSel.value).key = '';
  settingKey.value = '';
  await reloadPanel();
  addMessage('sys', result && result.restarted
    ? `Saved. Iter restarted on ${providerSel.value} · ${chosenModel()}.`
    : `Saved: ${providerSel.value} · ${chosenModel()}. Press Start when you are ready.`);
});

const settingHistory = document.getElementById('setting-history');
// M14-A5: the apps folder is shown here and changed only by its chooser (never by Save settings).
const settingVault = document.getElementById('setting-vault');
const chooseVaultButton = document.getElementById('btn-choose-vault');
if (chooseVaultButton) {
  chooseVaultButton.addEventListener('click', async () => {
    const result = await window.iterApi.chooseVault();
    if (result && result.vault && settingVault) settingVault.value = result.vault;
  });
}

// Start and "Save settings" save the form as it is (main merges it onto what is stored; an empty key keeps the
// stored one; nothing restarts).
async function saveSettingsFromForm() {
  await window.iterApi.saveSettings({
    ...panelChange(),
    // M11-C2: unchecked deletes the history file at once (main.js settings:save).
    keepHistory: settingHistory ? settingHistory.checked : panel.keepHistory !== false,
  });
}
document.getElementById('btn-save-settings').addEventListener('click', () => {
  saveSettingsFromForm().then(() => addMessage('sys', 'Settings saved. Restart Iter (Stop, then Start), or use Save & apply, for a new model to take effect.'));
});

async function reloadPanel() {
  panel = await window.iterApi.loadSettings();
  openaiCatalog = panel.openaiCatalog || { models: [] };
  for (const id of Object.keys(drafts)) delete drafts[id];
  providerSel.replaceChildren(...Object.entries(panel.providers || {}).map(([id, p]) => new Option(p.label, id)));
  providerSel.value = panel.provider || 'openrouter';
  showProvider();
  paintOpenAIUsage(panel.lastModelUsage);
  if (settingHistory) settingHistory.checked = panel.keepHistory !== false;
  if (settingVault) settingVault.value = panel.vault || '';
}
reloadPanel();

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
  'soul': { label: 'Soul', desc: 'Soul -- who is here, which Soul features are on, how often and in what tone. Per person; nothing here gates anything.' },
  'state-mgmt': { label: 'State', desc: 'Export, import, or reset Iter\u2019s accumulated memory and knowledge files.' },
  'tab-groups': { label: 'Groups', desc: 'Tab Groups -- save your open tabs as a named group; reopen, switch to, or close it later.' },
  'closed-tabs': { label: 'Closed', desc: 'Recently Closed -- the last 20 tabs you closed, most recent first. Reopen any of them.' },
  'permissions': { label: 'Perms', desc: 'Permissions -- camera and microphone access for Iter Browser.' },
  'termfiles': { label: 'Terminal', desc: 'Terminal & Files -- browse/edit files under iter/ and run shell commands.' },
  'activity': { label: 'Activity', desc: 'Iter\u2019s process output log.' },
};
const DOCK_DEFAULT_ORDER = ['settings', 'soul', 'state-mgmt', 'tab-groups', 'closed-tabs', 'permissions', 'termfiles', 'activity'];

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


// ---------------------------------------------------------------------
// Soul panel (docs/milestones/M6_soul_base.md section B). Per person: the
// selector switches whose settings are shown and who answers cards.
// ---------------------------------------------------------------------
const SOUL_DEFAULTS = { features: { forks: true, brief: true, read: false, wonder: false, felt: false, browsing_ally: false, margin: true },
  frequency: 'occasional', tone: 'warm', budget_per_cycle: 1, mode: 'open' };
const SOUL_MODES = ['open', 'jam', 'quiet', 'critique', 'museum'];
let soulSettings = { schema_version: 1, person: 'guest', people: {} };

function soulProfile(person) {
  const saved = soulSettings.people[person] || {};
  return { features: { ...SOUL_DEFAULTS.features, ...(saved.features || {}) },
    frequency: saved.frequency || SOUL_DEFAULTS.frequency, tone: saved.tone || SOUL_DEFAULTS.tone,
    mode: SOUL_MODES.includes(saved.mode) ? saved.mode : SOUL_DEFAULTS.mode,
    budget_per_cycle: Number.isInteger(saved.budget_per_cycle) ? saved.budget_per_cycle : SOUL_DEFAULTS.budget_per_cycle };
}

function showSoulProfile(person) {
  const profile = soulProfile(person);
  document.getElementById('soul-person').value = person;
  document.querySelectorAll('[data-soul-feature]').forEach((box) => { box.checked = !!profile.features[box.dataset.soulFeature]; });
  document.getElementById('soul-frequency').value = profile.frequency;
  document.getElementById('soul-tone').value = profile.tone;
  const modeSelect = document.getElementById('soul-mode');
  if (modeSelect) modeSelect.value = profile.mode;
  document.getElementById('soul-budget').value = String(profile.budget_per_cycle);
}

function readSoulForm() {
  const person = document.getElementById('soul-person').value;
  const features = {};
  document.querySelectorAll('[data-soul-feature]').forEach((box) => { features[box.dataset.soulFeature] = box.checked; });
  const budget = Math.max(0, Math.min(8, parseInt(document.getElementById('soul-budget').value, 10) || 0));
  return { ...soulSettings, person, people: { ...soulSettings.people,
    [person]: { features, frequency: document.getElementById('soul-frequency').value,
      tone: document.getElementById('soul-tone').value, budget_per_cycle: budget,
      mode: (document.getElementById('soul-mode') || { value: 'open' }).value } } };
}

if (document.getElementById('soul-person') && window.iterApi.loadSoulSettings) {
  Promise.resolve(window.iterApi.loadSoulSettings()).then((loaded) => {
    if (loaded && typeof loaded === 'object' && loaded.people) soulSettings = loaded;
    showSoulProfile(soulSettings.person || 'guest');
  }).catch(() => showSoulProfile('guest'));
  // Switching who is here shows that person's settings; Save makes it current.
  document.getElementById('soul-person').addEventListener('change', (event) => showSoulProfile(event.target.value));
  document.getElementById('btn-save-soul').addEventListener('click', async () => {
    const status = document.getElementById('soul-status');
    try {
      soulSettings = await window.iterApi.saveSoulSettings(readSoulForm());
      status.textContent = 'Saved for ' + soulSettings.person + '.';
    } catch (error) {
      status.textContent = 'Could not save: ' + (error && error.message ? error.message : error);
    }
  });
  // Forget acts on the saved current person (main.js reads it), so save first if the selector changed.
  const forget = document.getElementById('btn-soul-forget');
  if (forget && window.iterApi.forgetSoulTaste) {
    forget.addEventListener('click', async () => {
      const status = document.getElementById('soul-forget-status');
      try {
        const result = await window.iterApi.forgetSoulTaste();
        status.textContent = `Forgot ${result.deleted} belief${result.deleted === 1 ? '' : 's'} for ${result.person}.`;
      } catch (error) {
        status.textContent = 'Could not forget: ' + (error && error.message ? error.message : error);
      }
    });
  }
}
