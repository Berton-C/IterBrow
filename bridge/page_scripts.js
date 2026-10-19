// Page scripts for the builder's eyes (docs/milestones/M13_builder_eyes.md section B1). Pure: every
// function returns a self-contained JavaScript expression string that tab_manager.js runs in the page with
// executeJavaScript (and the tests run in Playwright). Caller values are embedded as JSON data, never code.
//
// An element is named back to Iter by its summary: {tag, id, text} (text: 60 characters of innerText, or an
// input's value).
'use strict';

// Shared in-page helpers, inlined into each script (a page script cannot import).
const HELPERS = `
  const summaryOf = (el) => {
    if (!el || el.nodeType !== 1) return null;
    const isField = el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement;
    const raw = isField ? String(el.value || '') : String(el.innerText || el.textContent || '');
    return { tag: el.tagName.toLowerCase(), id: el.id || '', text: raw.replace(/\\s+/g, ' ').trim().slice(0, 60) };
  };
  const shownWhy = (el) => {
    const style = getComputedStyle(el);
    if (style.display === 'none') return 'display: none';
    if (style.visibility === 'hidden' || style.visibility === 'collapse') return 'visibility: hidden';
    const rect = el.getBoundingClientRect();
    if (!el.getClientRects().length || rect.width <= 0 || rect.height <= 0) return 'zero size';
    return '';
  };
  const editableOf = (el) => !!el && (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement
    || el instanceof HTMLSelectElement || el.isContentEditable === true);
`;

function locateScript(selector) {
  return `(() => {${HELPERS}
  const selector = ${JSON.stringify(String(selector))};
  let el;
  try { el = document.querySelector(selector); } catch (error) { return { error: 'invalid' }; }
  if (!el) return { error: 'missing' };
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const rect = el.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  let reason = shownWhy(el);
  if (!reason && (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight)) reason = 'outside the viewport';
  const visible = !reason;
  let covered = false;
  let coveredBy = null;
  if (visible) {
    const hit = document.elementFromPoint(x, y);
    if (hit && hit !== el && !el.contains(hit)) { covered = true; coveredBy = summaryOf(hit); }
  }
  return { rect: { x, y, width: rect.width, height: rect.height }, visible, reason, covered, coveredBy,
           summary: summaryOf(el), editable: editableOf(el) };
})()`;
}

function stateScript() {
  return `(() => {${HELPERS}
  const active = document.activeElement && document.activeElement !== document.body && document.activeElement !== document.documentElement
    ? document.activeElement : null;
  return { url: location.href, title: document.title, active: summaryOf(active), activeEditable: editableOf(active) };
})()`;
}

function waitScript({ selector = '', text = '', url = '', timeoutMs = 10000 } = {}) {
  const input = { selector: String(selector || ''), text: String(text || ''), url: String(url || ''),
    timeoutMs: Math.max(0, Number(timeoutMs) || 0) };
  return `(async () => {${HELPERS}
  const input = ${JSON.stringify(input)};
  const started = Date.now();
  const deadline = started + input.timeoutMs;
  const check = () => {
    let match = null;
    if (input.selector) {
      let el;
      try { el = document.querySelector(input.selector); } catch (error) { return { invalid: true }; }
      if (!el || shownWhy(el)) return null;
      match = summaryOf(el);
    }
    if (input.text) {
      const body = document.body ? document.body.innerText : '';
      const at = body.indexOf(input.text);
      if (at < 0) return null;
      if (!match) match = body.slice(Math.max(0, at - 30), at + input.text.length + 30).replace(/\\s+/g, ' ').trim();
    }
    if (input.url) {
      if (!location.href.includes(input.url)) return null;
      if (!match) match = location.href;
    }
    return { match };
  };
  for (;;) {
    const result = check();
    if (result && result.invalid) return { found: false, afterMs: Date.now() - started, error: 'invalid selector' };
    if (result) return { found: true, afterMs: Date.now() - started, match: result.match };
    if (Date.now() >= deadline) return { found: false, afterMs: Date.now() - started };
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
})()`;
}

function scrollScript({ selector = '', x = 0, y = 0 } = {}) {
  const input = { selector: String(selector || ''), x: Number(x) || 0, y: Number(y) || 0 };
  return `(() => {${HELPERS}
  const input = ${JSON.stringify(input)};
  if (input.selector) {
    let el;
    try { el = document.querySelector(input.selector); } catch (error) { return { error: 'invalid' }; }
    if (!el) return { error: 'missing' };
    el.scrollIntoView({ block: 'center', inline: 'center' });
    return { target: summaryOf(el) };
  }
  // The nearest scrollable container of what has focus, else the window.
  let box = document.activeElement;
  while (box && box !== document.body && box !== document.documentElement) {
    const style = getComputedStyle(box);
    const scrollsY = /(auto|scroll)/.test(style.overflowY) && box.scrollHeight > box.clientHeight;
    const scrollsX = /(auto|scroll)/.test(style.overflowX) && box.scrollWidth > box.clientWidth;
    if (scrollsY || scrollsX) break;
    box = box.parentElement;
  }
  if (box && box !== document.body && box !== document.documentElement) {
    const before = { x: box.scrollLeft, y: box.scrollTop };
    box.scrollBy(input.x, input.y);
    return { container: summaryOf(box), before, after: { x: box.scrollLeft, y: box.scrollTop } };
  }
  const before = { x: window.scrollX, y: window.scrollY };
  window.scrollBy(input.x, input.y);
  return { container: null, before, after: { x: window.scrollX, y: window.scrollY } };
})()`;
}

// The scripted probe (moved from foundry_apps.js, which re-exports it). Synthetic click/fill steps, then
// observations; `ready` reports the app's data-iter-ready flag without requiring it.
function probeScript(spec) {
  return `(${async function runProbe(input) {
    const deadline = Date.now() + input.timeoutMs;
    const observations = [];
    for (const step of input.steps) {
      if (Date.now() >= deadline) throw new Error('Probe deadline exceeded');
      const element = document.querySelector(step.selector);
      if (!element) throw new Error('Interaction target is absent: ' + step.selector);
      if (step.kind === 'click') element.click();
      else {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement)) {
          throw new Error('Fill requires an input, textarea or select');
        }
        element.value = step.value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
      }
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    // Give asynchronous command/read-back handlers a bounded settling window.
    await new Promise((resolve) => setTimeout(resolve, Math.min(150, Math.max(0, deadline - Date.now()))));
    for (const item of input.assertions) {
      const matches = document.querySelectorAll(item.selector);
      const element = matches[0];
      let actual = null;
      if (item.kind === 'count') actual = matches.length;
      if (item.kind === 'text') actual = element ? String(element.textContent).slice(0, 8192) : null;
      if (item.kind === 'value') actual = element && 'value' in element ? String(element.value).slice(0, 8192) : null;
      if (item.kind === 'visible') {
        const style = element ? getComputedStyle(element) : null;
        actual = !!element && element.getClientRects().length > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      }
      observations.push({ kind: item.kind, selector: item.selector, actual, expected: item.expected });
    }
    return { observations, title: document.title, ready: !!document.body && document.body.dataset.iterReady === 'true' };
  }.toString()})(${JSON.stringify(spec)})`;
}

module.exports = { locateScript, stateScript, waitScript, scrollScript, probeScript };
