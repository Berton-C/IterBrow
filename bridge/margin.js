// The margin: the Soul in the tab (docs/milestones/M8_soul_presence.md section D1).
//
// Pure DOM. A small glyph sits in the corner of an app tab; it remembers the last element the
// person pointed at, and opens a panel where they can ask about it or ask Iter to jam on it.
// Nothing here talks to Iter directly: `api.send` does (the preload passes an IPC-backed api,
// and main.js decides from the tab's app scope, its lock and the saved person whether the
// margin is allowed at all). Styles are inline on the nodes it creates; no stylesheet is
// injected and the page's own CSS is never touched. Everything lives under one root node, so
// turning the margin off removes one node and one listener.
(function (root) {
  'use strict';

  const ROOT_ID = 'iter-margin-root';
  const TEXT_LIMIT = 80;

  function style(node, rules) {
    Object.assign(node.style, rules);
    return node;
  }

  function el(doc, tag, props, rules) {
    const node = doc.createElement(tag);
    Object.assign(node, props || {});
    return rules ? style(node, rules) : node;
  }

  function selectorFor(element) {
    if (!element || element.nodeType !== 1) return null;
    if (element.id) return '#' + element.id;
    const tag = element.tagName.toLowerCase();
    const classes = Array.from(element.classList || []).filter((name) => /^[A-Za-z_-][\w-]*$/.test(name));
    if (classes.length) return tag + '.' + classes.join('.');
    // A short nth-of-type path: at most four levels, stopping at an id or the body.
    const parts = [];
    let node = element;
    while (node && node.nodeType === 1 && parts.length < 4) {
      const name = node.tagName.toLowerCase();
      if (node.id) { parts.unshift('#' + node.id); break; }
      if (name === 'body' || name === 'html') { parts.unshift(name); break; }
      let index = 1;
      for (let sibling = node.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
        if (sibling.tagName === node.tagName) index += 1;
      }
      parts.unshift(`${name}:nth-of-type(${index})`);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }

  function describe(element) {
    const selector = selectorFor(element);
    if (!selector) return null;
    const text = String(element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, TEXT_LIMIT);
    return { selector, tag: element.tagName.toLowerCase(), text };
  }

  function installMargin(doc, api) {
    let state = null; // { root, onMove } while installed
    let pointed = null;
    let installing = false;

    function remove() {
      if (!state) return;
      doc.removeEventListener('mousemove', state.onMove, true);
      doc.removeEventListener('keydown', state.onKey, true);
      if (state.root.parentNode) state.root.parentNode.removeChild(state.root);
      state = null;
      pointed = null;
    }

    function build() {
      if (state || doc.getElementById(ROOT_ID)) return;
      const host = el(doc, 'div', { id: ROOT_ID });
      const glyph = el(doc, 'button', { id: 'iter-margin-glyph', type: 'button', textContent: '✦', title: 'Ask Iter about this page' }, {
        position: 'fixed', right: '10px', bottom: '10px', zIndex: '2147483646', width: '22px', height: '22px',
        padding: '0', border: 'none', borderRadius: '11px', background: 'transparent', color: '#8a6cd1',
        fontSize: '14px', lineHeight: '22px', cursor: 'pointer', opacity: '0.35', transition: 'opacity 120ms ease',
      });
      glyph.setAttribute('aria-label', 'Iter');
      glyph.addEventListener('mouseenter', () => { glyph.style.opacity = '0.9'; });
      glyph.addEventListener('mouseleave', () => { glyph.style.opacity = '0.35'; });
      host.appendChild(glyph);

      let panel = null;
      function closePanel() {
        if (panel && panel.parentNode) panel.parentNode.removeChild(panel);
        panel = null;
      }
      function openPanel() {
        if (panel) return;
        panel = el(doc, 'div', { id: 'iter-margin' }, {
          position: 'fixed', right: '10px', bottom: '40px', zIndex: '2147483647', width: '280px', boxSizing: 'border-box',
          padding: '10px', borderRadius: '10px', background: 'rgba(28, 24, 36, 0.96)', color: '#eee',
          font: '12px/1.4 -apple-system, system-ui, sans-serif', boxShadow: '0 6px 24px rgba(0,0,0,0.3)',
        });
        const target = el(doc, 'div', { id: 'iter-margin-target', textContent: 'pointing at: ' + (pointed ? pointed.selector : 'the page') },
          { opacity: '0.7', marginBottom: '6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' });
        const text = el(doc, 'textarea', { id: 'iter-margin-text', rows: 3, placeholder: 'ask, or leave empty and jam' }, {
          width: '100%', boxSizing: 'border-box', resize: 'vertical', borderRadius: '6px', border: '1px solid #554',
          background: '#171420', color: '#eee', padding: '6px', font: 'inherit',
        });
        const row = el(doc, 'div', {}, { display: 'flex', gap: '6px', marginTop: '6px', alignItems: 'center' });
        const button = (id, label) => el(doc, 'button', { id, type: 'button', textContent: label }, {
          border: '1px solid #665', borderRadius: '6px', background: '#2b2538', color: '#eee', padding: '4px 8px',
          font: 'inherit', cursor: 'pointer',
        });
        const ask = button('iter-margin-ask', 'Ask about this');
        const jam = button('iter-margin-jam', 'Jam on this');
        const close = button('iter-margin-close', '×');
        close.setAttribute('aria-label', 'Close');
        style(close, { marginLeft: 'auto' });
        const status = el(doc, 'div', { id: 'iter-margin-status' }, { minHeight: '14px', marginTop: '4px', opacity: '0.8' });
        row.append(ask, jam, close);
        panel.append(target, text, row, status);
        host.appendChild(panel);

        function submit(intent) {
          const value = text.value.trim();
          if (intent === 'ask' && !value) {
            status.textContent = "say what you'd like to ask";
            return;
          }
          ask.disabled = true;
          jam.disabled = true;
          status.textContent = '';
          Promise.resolve()
            .then(() => api.send({ intent, text: value, element: pointed }))
            .then(() => {
              status.textContent = 'sent';
              text.value = '';
            })
            .catch((error) => {
              status.textContent = (error && error.message) ? error.message : String(error);
            })
            .finally(() => {
              ask.disabled = false;
              jam.disabled = false;
            });
        }
        ask.addEventListener('click', () => submit('ask'));
        jam.addEventListener('click', () => submit('jam'));
        close.addEventListener('click', closePanel);
      }
      glyph.addEventListener('click', () => (panel ? closePanel() : openPanel()));

      const onMove = (event) => {
        const target = event.target;
        if (!target || target.nodeType !== 1 || host.contains(target)) return;
        pointed = describe(target);
        const label = doc.getElementById('iter-margin-target');
        if (label) label.textContent = 'pointing at: ' + (pointed ? pointed.selector : 'the page');
      };
      const onKey = (event) => { if (event.key === 'Escape') closePanel(); };
      doc.addEventListener('mousemove', onMove, true);
      doc.addEventListener('keydown', onKey, true);
      (doc.body || doc.documentElement).appendChild(host);
      state = { root: host, onMove, onKey };
    }

    function install() {
      if (state || installing) return Promise.resolve();
      installing = true;
      return Promise.resolve()
        .then(() => api.enabled())
        .then((answer) => { if (answer && answer.enabled) build(); })
        .catch(() => {})
        .finally(() => { installing = false; });
    }

    if (typeof api.onState === 'function') {
      api.onState((next) => {
        if (next && next.enabled) {
          if (!state) build();
        } else {
          remove();
        }
      });
    }
    install();
    return { remove, selectorFor, describe };
  }

  const exported = { installMargin, selectorFor };
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
  else root.IterMargin = exported;
}(typeof window !== 'undefined' ? window : this));
