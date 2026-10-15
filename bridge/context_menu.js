// Right-click (two-finger click) context menu for every surface: the sidebar,
// toolbar and tab strip views and each browser tab.
//
// Electron's spellchecker already underlines misspellings; without a
// 'context-menu' handler nothing ever showed, so no corrections were offered.
// buildTemplate() is pure (params in, menu template out) so it is tested under
// plain node; attach() wires it to a WebContents with Electron's Menu.
'use strict';

function item(label, click, extra = {}) {
  return { label, click, ...extra };
}

function separator() {
  return { type: 'separator' };
}

function trim(text, max = 40) {
  const flat = String(text || '').replace(/\s+/g, ' ').trim();
  return flat.length > max ? flat.slice(0, max - 1) + '…' : flat;
}

// params: Electron's context-menu event params (misspelledWord,
// dictionarySuggestions, isEditable, selectionText, linkURL, srcURL,
// mediaType, editFlags, ...). actions: callbacks the caller provides; a menu
// item appears only when its action exists.
function buildTemplate(params = {}, actions = {}) {
  const template = [];
  const flags = params.editFlags || {};
  const selection = String(params.selectionText || '');

  if (params.misspelledWord && actions.replaceMisspelling) {
    const suggestions = (params.dictionarySuggestions || []).slice(0, 6);
    if (suggestions.length) {
      for (const word of suggestions) template.push(item(word, () => actions.replaceMisspelling(word)));
    } else {
      template.push(item('No Guesses Found', null, { enabled: false }));
    }
    if (actions.addToDictionary) {
      template.push(item('Add to Dictionary', () => actions.addToDictionary(params.misspelledWord)));
    }
    template.push(separator());
  }

  if (params.linkURL && actions.openLinkInNewTab) {
    template.push(item('Open Link in New Tab', () => actions.openLinkInNewTab(params.linkURL)));
    if (actions.copyText) template.push(item('Copy Link', () => actions.copyText(params.linkURL)));
    template.push(separator());
  }

  if (params.mediaType === 'image' && params.srcURL) {
    if (actions.openLinkInNewTab) template.push(item('Open Image in New Tab', () => actions.openLinkInNewTab(params.srcURL)));
    if (actions.copyText) template.push(item('Copy Image Address', () => actions.copyText(params.srcURL)));
    template.push(separator());
  }

  if (params.isEditable) {
    if (actions.undo) template.push(item('Undo', actions.undo, { enabled: flags.canUndo !== false, accelerator: 'CmdOrCtrl+Z' }));
    if (actions.redo) template.push(item('Redo', actions.redo, { enabled: flags.canRedo !== false, accelerator: 'Shift+CmdOrCtrl+Z' }));
    if (actions.undo || actions.redo) template.push(separator());
    if (actions.cut) template.push(item('Cut', actions.cut, { enabled: flags.canCut !== false, accelerator: 'CmdOrCtrl+X' }));
    if (actions.copy) template.push(item('Copy', actions.copy, { enabled: flags.canCopy !== false, accelerator: 'CmdOrCtrl+C' }));
    if (actions.paste) template.push(item('Paste', actions.paste, { enabled: flags.canPaste !== false, accelerator: 'CmdOrCtrl+V' }));
    if (actions.selectAll) template.push(item('Select All', actions.selectAll, { enabled: flags.canSelectAll !== false, accelerator: 'CmdOrCtrl+A' }));
    template.push(separator());
  } else if (selection) {
    if (actions.copy) template.push(item('Copy', actions.copy, { accelerator: 'CmdOrCtrl+C' }));
    if (actions.searchSelection) template.push(item(`Search for “${trim(selection)}”`, () => actions.searchSelection(selection)));
    template.push(separator());
  }

  if (actions.back || actions.forward || actions.reload) {
    if (actions.back) template.push(item('Back', actions.back, { enabled: params.canGoBack !== false }));
    if (actions.forward) template.push(item('Forward', actions.forward, { enabled: params.canGoForward !== false }));
    if (actions.reload) template.push(item('Reload', actions.reload));
    template.push(separator());
  }

  if (actions.inspect) template.push(item('Inspect Element', () => actions.inspect(params.x || 0, params.y || 0)));

  // Trim a trailing or doubled separator so the menu never ends with a rule.
  const cleaned = [];
  for (const entry of template) {
    if (entry.type === 'separator' && (!cleaned.length || cleaned[cleaned.length - 1].type === 'separator')) continue;
    cleaned.push(entry);
  }
  while (cleaned.length && cleaned[cleaned.length - 1].type === 'separator') cleaned.pop();
  return cleaned;
}

// Standard actions every WebContents gets; `extra` adds surface-specific ones
// (tabs add back/forward/reload and open-in-new-tab).
function standardActions(contents, extra = {}) {
  const { clipboard, session } = require('electron');
  return {
    replaceMisspelling: (word) => contents.replaceMisspelling(word),
    addToDictionary: (word) => (contents.session || session.defaultSession).addWordToSpellCheckerDictionary(word),
    undo: () => contents.undo(),
    redo: () => contents.redo(),
    cut: () => contents.cut(),
    copy: () => contents.copy(),
    paste: () => contents.paste(),
    selectAll: () => contents.selectAll(),
    copyText: (text) => clipboard.writeText(String(text)),
    inspect: (x, y) => contents.inspectElement(x, y),
    ...extra,
  };
}

function attach(contents, extra = {}, getWindow = () => null) {
  const { Menu } = require('electron');
  contents.on('context-menu', (event, params) => {
    event.preventDefault();
    const template = buildTemplate(params, standardActions(contents, extra));
    if (!template.length) return;
    // No x/y: Electron then opens the menu at the cursor, which is right for a
    // view that is offset inside the window (params.x/y are view-relative).
    const popup = {};
    const window = getWindow();
    if (window) popup.window = window;
    Menu.buildFromTemplate(template).popup(popup);
  });
}

module.exports = { buildTemplate, standardActions, attach };
