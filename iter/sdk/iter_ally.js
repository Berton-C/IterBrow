// IterAlly — the ally an app inherits from IterBrow (docs/milestones/M10_ally_sdk.md section A).
//
// One file, no dependencies. A static page includes it and calls
//   IterAlly.install({ brief: { for, flourishing }, person, model? })
// and gets the Soul's lens (read from soul_kernel.js / soul_kernel.json, generated from the kernel
// atoms -- this file contains no pattern names or text), cards and forks that return the person's
// pick, a passing notice, and a calibration record the app keeps for itself.
//
// Three guarantees:
//   - No gate. Nothing here can block, pause or veto the app; a card only returns a pick.
//   - Never phones home. The only network request is to the app owner's own model, and only when
//     they configured one (IterAlly.ask). The kernel loads from a file next to this one.
//   - The brief is the app's Soul: who it is for, and what flourishing looks like for them.
(function (root) {
  'use strict';

  const CARD_KINDS = ['fork', 'brief', 'read', 'offer', 'note'];
  const STORAGE_KEY = 'iter-ally.calibration';
  const FACET_NAMES = ['description', 'flourishing', 'captured', 'signal', 'felt', 'moat', 'anti', 'proxy', 'gap'];
  const IDENT = /^[A-Za-z0-9_-]{1,40}$/;
  const scriptSrc = (typeof document !== 'undefined' && document.currentScript && document.currentScript.src) || '';

  let state = null; // { brief, person, model, kernel }
  let memoryCalibration = [];
  const queue = [];
  let showing = false;

  // ---- helpers ------------------------------------------------------------------------------
  function fail(message) { throw new Error('IterAlly: ' + message); }

  function installed() {
    if (!state || !state.kernel) fail('not installed yet');
    return state;
  }

  function cleanBrief(brief) {
    const ok = brief && typeof brief.for === 'string' && typeof brief.flourishing === 'string'
      && brief.for.trim() && brief.flourishing.trim() && brief.for.length <= 200 && brief.flourishing.length <= 200;
    if (!ok) fail('a brief needs "for" and "flourishing"');
    return { for: brief.for.trim(), flourishing: brief.flourishing.trim() };
  }

  function validKernel(kernel) {
    return kernel && Array.isArray(kernel.patterns) && kernel.facets && typeof kernel.facets === 'object' && Array.isArray(kernel.pairs);
  }

  function siblingUrl(name) {
    if (!scriptSrc) return name;
    return scriptSrc.replace(/[^/]*([?#].*)?$/, name);
  }

  // The kernel loads with a <script> tag (works from file://, where fetch() is refused).
  function loadKernel() {
    if (validKernel(root.IterAllyKernel)) return Promise.resolve(root.IterAllyKernel);
    return new Promise((resolve, reject) => {
      const tag = document.createElement('script');
      tag.src = siblingUrl('soul_kernel.js');
      tag.onload = () => (validKernel(root.IterAllyKernel) ? resolve(root.IterAllyKernel) : reject(new Error('IterAlly: soul_kernel.js did not define the kernel')));
      tag.onerror = () => reject(new Error('IterAlly: could not load soul_kernel.js next to iter_ally.js'));
      (document.head || document.documentElement).appendChild(tag);
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // A very small, safe markdown: escape first, then **bold**, *em*, `code`, line breaks.
  function markdown(text) {
    return escapeHtml(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  function style(node, rules) { Object.assign(node.style, rules); return node; }

  const BASE = { margin: '0', boxSizing: 'border-box', font: '13px/1.45 -apple-system, system-ui, sans-serif', color: '#eee',
    letterSpacing: 'normal', textTransform: 'none', textAlign: 'left', textShadow: 'none', boxShadow: 'none' };

  function el(tag, props, rules) {
    const node = document.createElement(tag);
    Object.assign(node, props || {});
    return style(node, Object.assign({}, BASE, rules || {}));
  }

  function rootNode() {
    let host = document.getElementById('iter-ally-root');
    if (!host) {
      host = el('div', { id: 'iter-ally-root' }, { position: 'fixed', right: '14px', bottom: '14px', zIndex: '2147483646',
        width: '300px', display: 'flex', flexDirection: 'column', gap: '8px', pointerEvents: 'none' });
      (document.body || document.documentElement).appendChild(host);
    }
    return host;
  }

  // ---- calibration --------------------------------------------------------------------------
  function readCalibration() {
    try {
      const raw = root.localStorage && root.localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) { /* blocked storage: memory only */ }
    return memoryCalibration.slice();
  }

  function writeCalibration(entries) {
    memoryCalibration = entries.slice();
    try { if (root.localStorage) root.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries)); } catch (_) {}
  }

  function record(entry) {
    const entries = readCalibration();
    entries.push(entry);
    writeCalibration(entries);
  }

  // ---- cards --------------------------------------------------------------------------------
  function cleanChoices(raw) {
    const known = installed().kernel.patterns;
    if (!Array.isArray(raw) || raw.length < 1 || raw.length > 3) fail('a card has 1 to 3 choices');
    const ids = new Set();
    return raw.map((item, index) => {
      const choice = typeof item === 'string' ? { label: item } : (item || {});
      if (typeof choice.label !== 'string' || !choice.label.trim()) fail('every choice needs a label');
      const id = String(choice.id || 'abc'[index] || String(index));
      if (id === 'dismiss' || ids.has(id)) fail('choice ids must be distinct and not "dismiss"');
      ids.add(id);
      if (choice.pattern !== undefined && !known.includes(choice.pattern)) fail('unknown pattern ' + choice.pattern);
      return { id, label: choice.label.trim(), hint: choice.hint ? String(choice.hint) : '', pattern: choice.pattern || null };
    });
  }

  function showNext() {
    if (showing || !queue.length) return;
    showing = true;
    const { card, resolve } = queue.shift();
    const host = rootNode();
    const box = el('div', { className: 'iter-ally-card iter-ally-card-' + card.kind }, {
      pointerEvents: 'auto', padding: '12px', borderRadius: '10px', background: 'rgba(28, 24, 36, 0.96)',
      boxShadow: '0 6px 24px rgba(0,0,0,0.3)' });
    const head = el('div', {}, { display: 'flex', alignItems: 'flex-start', gap: '8px' });
    const title = el('div', { className: 'iter-ally-title', textContent: card.title }, { fontWeight: '600', flex: '1 1 auto' });
    const dismiss = el('button', { className: 'iter-ally-dismiss', type: 'button', textContent: '×', title: 'Dismiss' }, {
      border: 'none', background: 'transparent', cursor: 'pointer', padding: '0 2px', fontSize: '15px', lineHeight: '1' });
    dismiss.setAttribute('aria-label', 'Dismiss');
    head.append(title, dismiss);
    box.appendChild(head);
    if (card.body) {
      const body = el('div', { className: 'iter-ally-body' }, { marginTop: '6px', opacity: '0.9' });
      body.innerHTML = markdown(card.body);
      box.appendChild(body);
    }
    const row = el('div', {}, { display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '10px' });
    card.choices.forEach((choice) => {
      const button = el('button', { className: 'iter-ally-choice', type: 'button', textContent: choice.label, title: choice.hint }, {
        border: '1px solid #665', borderRadius: '6px', background: '#2b2538', padding: '4px 10px', cursor: 'pointer' });
      button.dataset.choice = choice.id;
      button.addEventListener('click', () => finish(choice.id));
      row.appendChild(button);
    });
    box.appendChild(row);
    host.appendChild(box);
    let done = false;
    function finish(pick) {
      if (done) return;
      done = true;
      record({ at: Date.now(), kind: card.kind, topic: card.topic, pick, person: state.person });
      if (box.parentNode) box.parentNode.removeChild(box);
      showing = false;
      resolve(pick);
      showNext();
    }
    dismiss.addEventListener('click', () => finish('dismiss'));
  }

  function card(spec) {
    installed();
    const value = spec || {};
    if (!CARD_KINDS.includes(value.kind)) fail('kind must be one of ' + CARD_KINDS.join(', '));
    if (typeof value.title !== 'string' || !value.title.trim()) fail('a card needs a title');
    const prepared = {
      kind: value.kind, title: value.title.trim(), body: typeof value.body === 'string' ? value.body : '',
      choices: cleanChoices(value.choices), topic: typeof value.topic === 'string' && value.topic ? value.topic : null,
    };
    return new Promise((resolve) => {
      queue.push({ card: prepared, resolve });
      showNext();
    });
  }

  function fork(spec) {
    const value = spec || {};
    const a = value.a || {};
    const b = value.b || {};
    if (!paraconsistent(a.pattern, b.pattern)) fail(a.pattern + ' and ' + b.pattern + ' are not a declared pair');
    const body = (value.body ? value.body + '\n\n' : '') + 'Both can be true at once; this is yours to choose.';
    return card({ kind: 'fork', title: value.title, body, topic: value.topic,
      choices: [{ id: 'a', label: a.label, pattern: a.pattern }, { id: 'b', label: b.label, pattern: b.pattern }] });
  }

  function notice(text) {
    installed();
    const host = rootNode();
    const line = el('div', { className: 'iter-ally-notice', textContent: '✦ ' + String(text || '') }, {
      pointerEvents: 'none', padding: '8px 12px', borderRadius: '10px', background: 'rgba(28, 24, 36, 0.9)', fontStyle: 'italic' });
    host.appendChild(line);
    setTimeout(() => { if (line.parentNode) line.parentNode.removeChild(line); }, 6000);
  }

  // ---- the lens -----------------------------------------------------------------------------
  function patterns() { return installed().kernel.patterns.slice(); }
  function facet(pattern, name) {
    if (!FACET_NAMES.includes(name)) fail('unknown facet ' + name);
    const entry = installed().kernel.facets[pattern];
    return entry ? (entry[name] || '') : '';
  }
  function gap(pattern) { return facet(pattern, 'gap'); }
  function pairs() { return installed().kernel.pairs.map((pair) => pair.slice()); }
  function paraconsistent(a, b) {
    return installed().kernel.pairs.some((pair) => (pair[0] === a && pair[1] === b) || (pair[0] === b && pair[1] === a));
  }
  function brief() { return Object.assign({}, installed().brief); }

  function lensText() {
    const kernel = installed().kernel;
    return kernel.patterns.map((pattern) => {
      const entry = kernel.facets[pattern] || {};
      return '- ' + pattern + ' — ' + (entry.description || '') + (entry.gap ? ' Gap: ' + entry.gap : '');
    }).join('\n');
  }

  // ---- the model, optional ------------------------------------------------------------------
  function ask(text) {
    let current;
    try { current = installed(); } catch (error) { return Promise.reject(error); }
    const model = current.model;
    if (!model || !model.baseUrl || !model.model) return Promise.reject(new Error('IterAlly: no model configured'));
    const system = 'You are the ally inside an app. Its brief: it is for ' + current.brief.for
      + '. Flourishing looks like: ' + current.brief.flourishing
      + '. You offer; the person decides. Read the moment through this lens:\n' + lensText();
    const headers = { 'Content-Type': 'application/json' };
    if (model.apiKey) headers.Authorization = 'Bearer ' + model.apiKey;
    return root.fetch(String(model.baseUrl).replace(/\/+$/, '') + '/chat/completions', {
      method: 'POST', headers,
      body: JSON.stringify({ model: model.model, messages: [{ role: 'system', content: system }, { role: 'user', content: String(text || '') }] }),
    }).then((response) => {
      if (!response.ok) throw new Error('IterAlly: the model answered ' + response.status);
      return response.json();
    }).then((data) => String((data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) || ''));
  }

  // ---- install ------------------------------------------------------------------------------
  function install(options) {
    const value = options || {};
    const cleanedBrief = cleanBrief(value.brief);
    const person = typeof value.person === 'string' && IDENT.test(value.person) ? value.person : 'guest';
    const model = value.model && typeof value.model === 'object' ? {
      baseUrl: String(value.model.baseUrl || ''), apiKey: value.model.apiKey ? String(value.model.apiKey) : '', model: String(value.model.model || ''),
    } : null;
    const kernelReady = validKernel(value.kernel) ? Promise.resolve(value.kernel) : loadKernel();
    return kernelReady.then((kernel) => {
      state = { brief: cleanedBrief, person, model, kernel };
      return api;
    });
  }

  function calibration() { return readCalibration(); }
  function forget() { writeCalibration([]); }
  function calibrationExport() {
    const current = installed();
    return { app: typeof document !== 'undefined' ? document.title : '', person: current.person, brief: Object.assign({}, current.brief), picks: readCalibration() };
  }
  function exportCalibration() {
    const blob = new Blob([JSON.stringify(calibrationExport(), null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'iter_ally_calibration.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    return blob;
  }

  const api = { install, patterns, facet, gap, pairs, paraconsistent, brief, card, fork, notice, ask,
    calibration, forget, calibrationExport, exportCalibration };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.IterAlly = api;
}(typeof window !== 'undefined' ? window : globalThis));
