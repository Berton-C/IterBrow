// Pure tests for bridge/context_menu.js buildTemplate (no Electron needed).
const assert = require('assert');
const path = require('path');
const { buildTemplate } = require(path.join(__dirname, '..', '..', 'bridge', 'context_menu.js'));

const calls = [];
const actions = {
  replaceMisspelling: (w) => calls.push(['replace', w]),
  addToDictionary: (w) => calls.push(['add', w]),
  undo: () => calls.push(['undo']), redo: () => calls.push(['redo']),
  cut: () => calls.push(['cut']), copy: () => calls.push(['copy']), paste: () => calls.push(['paste']),
  selectAll: () => calls.push(['selectAll']),
  copyText: (t) => calls.push(['copyText', t]),
  openLinkInNewTab: (u) => calls.push(['open', u]),
  searchSelection: (t) => calls.push(['search', t]),
  back: () => calls.push(['back']), forward: () => calls.push(['forward']), reload: () => calls.push(['reload']),
  inspect: (x, y) => calls.push(['inspect', x, y]),
};
const labels = (t) => t.map((i) => i.type === 'separator' ? '---' : i.label);

// 1. Misspelled word in an editable: suggestions first, Add to Dictionary, then edit actions.
let t = buildTemplate({ misspelledWord: 'recieve', dictionarySuggestions: ['receive', 'relieve'], isEditable: true,
  editFlags: { canUndo: true, canRedo: false, canCut: true, canCopy: true, canPaste: true, canSelectAll: true } }, actions);
assert.deepStrictEqual(labels(t).slice(0, 4), ['receive', 'relieve', 'Add to Dictionary', '---']);
t[0].click(); t[2].click();
assert.deepStrictEqual(calls.splice(0), [['replace', 'receive'], ['add', 'recieve']]);
assert.strictEqual(t.find((i) => i.label === 'Redo').enabled, false);
assert.strictEqual(t.find((i) => i.label === 'Paste').enabled, true);
assert.strictEqual(labels(t)[labels(t).length - 1], 'Inspect Element');

// 2. Misspelled word with no suggestions: a disabled "No Guesses Found" instead of nothing.
t = buildTemplate({ misspelledWord: 'xqzt', dictionarySuggestions: [], isEditable: true, editFlags: {} }, actions);
assert.strictEqual(t[0].label, 'No Guesses Found');
assert.strictEqual(t[0].enabled, false);
assert.strictEqual(t[1].label, 'Add to Dictionary');

// 3. A link in a page: open in new tab + copy link, then page navigation.
t = buildTemplate({ linkURL: 'https://example.com/x', canGoBack: false, canGoForward: true }, actions);
assert.deepStrictEqual(labels(t), ['Open Link in New Tab', 'Copy Link', '---', 'Back', 'Forward', 'Reload', '---', 'Inspect Element']);
t[0].click(); t[1].click();
assert.deepStrictEqual(calls.splice(0), [['open', 'https://example.com/x'], ['copyText', 'https://example.com/x']]);
assert.strictEqual(t.find((i) => i.label === 'Back').enabled, false);
assert.strictEqual(t.find((i) => i.label === 'Forward').enabled, true);

// 4. Selected text outside an editable: copy + search with the selection trimmed.
t = buildTemplate({ selectionText: '  the   quick brown fox jumps over the lazy dog again and again  ' }, actions);
assert.strictEqual(t[0].label, 'Copy');
assert.ok(t[1].label.startsWith('Search for “the quick brown fox'), t[1].label);
assert.ok(t[1].label.endsWith('…”'), t[1].label);
t[1].click();
assert.deepStrictEqual(calls.splice(0)[0][0], 'search');

// 5. An image: open + copy address.
t = buildTemplate({ mediaType: 'image', srcURL: 'https://example.com/a.png' }, actions);
assert.deepStrictEqual(labels(t).slice(0, 2), ['Open Image in New Tab', 'Copy Image Address']);

// 6. UI views (no back/forward/reload actions) with plain text: only inspect; never a trailing separator.
t = buildTemplate({}, { inspect: actions.inspect });
assert.deepStrictEqual(labels(t), ['Inspect Element']);
t = buildTemplate({ isEditable: true, editFlags: {} }, { cut: actions.cut, copy: actions.copy, paste: actions.paste });
assert.deepStrictEqual(labels(t), ['Cut', 'Copy', 'Paste']);

// 7. Nothing applicable and no actions: an empty menu (attach() then shows nothing).
assert.deepStrictEqual(buildTemplate({}, {}), []);

console.log('context_menu_test: ok');
