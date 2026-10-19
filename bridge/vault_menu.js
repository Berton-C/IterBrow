// The Apps button's menu (docs/milestones/M14_vault_and_foundry_loop.md A4, B4). Pure: plain Electron menu
// template objects whose `click` calls one of the handlers main.js passes in, so the shape is tested in node.
//
//   appsMenuTemplate(catalog, state, handlers)
//     catalog  = local_apps.list_apps() ([{id, kind, brief}], vault apps first, kind "vault")
//     state    = {vault, recentVaults, undoable}  (undoable: vault app ids Iter has changed, with history)
//     handlers = {open(id), choose(), reveal(), switchTo(path), undo(id)}
//
// With a vault: its apps, Examples ▸ (shipped examples, crm, any Foundry projects), Choose / Reveal, Recent ▸,
// Undo. Without one: Examples ▸ and Choose only (a feature that is off leaves no trace).

function appLabel(app) {
  return app.brief && app.brief.for ? `${app.id} — for ${app.brief.for}` : app.id;
}

function appsMenuTemplate(catalog, state, handlers) {
  const apps = Array.isArray(catalog) ? catalog : [];
  const s = state || {};
  const h = handlers || {};
  const vault = s.vault || null;
  const items = [];
  const mine = apps.filter((app) => app.kind === 'vault');
  const others = apps.filter((app) => app.kind !== 'vault');
  if (vault) {
    if (mine.length) {
      for (const app of mine) items.push({ label: appLabel(app), click: () => h.open(app.id) });
    } else {
      items.push({ label: 'No apps in this folder yet', enabled: false });
    }
    items.push({ type: 'separator' });
  }
  items.push({
    label: 'Examples',
    submenu: others.length
      ? others.map((app) => ({ label: appLabel(app), click: () => h.open(app.id) }))
      : [{ label: 'No examples', enabled: false }],
  });
  items.push({ type: 'separator' });
  items.push({ label: 'Choose apps folder…', click: () => h.choose() });
  if (vault) {
    items.push({ label: 'Reveal apps folder', click: () => h.reveal() });
    const recent = (Array.isArray(s.recentVaults) ? s.recentVaults : []).filter((p) => p && p !== vault);
    if (recent.length) {
      items.push({ label: 'Recent', submenu: recent.slice(0, 5).map((p) => ({ label: p, click: () => h.switchTo(p) })) });
    }
    const undoable = Array.isArray(s.undoable) ? s.undoable : [];
    if (undoable.length) {
      items.push({ type: 'separator' });
      for (const id of undoable) items.push({ label: `Undo Iter's last change to ${id}`, click: () => h.undo(id) });
    }
  }
  return items;
}

// Recent vaults after choosing `chosen` while `previous` was open: newest first, unique, at most 5,
// never the vault now open.
function nextRecent(previous, recent, chosen) {
  const out = [];
  for (const p of [previous, ...(Array.isArray(recent) ? recent : [])]) {
    if (p && p !== chosen && !out.includes(p)) out.push(p);
  }
  return out.slice(0, 5);
}

module.exports = { appsMenuTemplate, nextRecent };
