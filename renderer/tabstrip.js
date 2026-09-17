// Full-width tab strip -- moved here from renderer.js/index.html on
// 2026-09-17 so tabs get the entire window width instead of being squeezed
// into the ~400px sidebar column. This view's own height is not fixed: it
// measures itself after every render/resize and reports the real height to
// the main process (see reportHeight() below), which repositions the
// sidebar/toolbar/page views to make room -- so the strip genuinely grows
// into a 2nd/3rd row as tabs wrap, and shrinks back as they're closed.
const tabstripEl = document.getElementById('tabstrip');
const tabstripScroll = document.getElementById('tabstrip-scroll');
const tabAllBtn = document.getElementById('tab-all');
const tabAllMenu = document.getElementById('tab-all-menu');

let activeTabId = null;
let tabsCache = [];
let dragTabId = null;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderTabs(list) {
  tabsCache = list;
  const active = list.find((t) => t.active);
  activeTabId = active ? active.id : null;

  tabstripScroll.innerHTML = '';
  for (const tab of list) {
    const pill = document.createElement('div');
    pill.className = 'tab-pill' + (tab.active ? ' active' : '') + (tab.locked ? ' locked' : '') + (tab.pinned ? ' pinned' : '');
    pill.title = tab.locked
      ? tab.url + ' (locked — Iter cannot alter or close this tab until you click the lock)'
      : tab.url;
    pill.draggable = true;
    pill.innerHTML = `<span class="pin" title="${tab.pinned ? 'Pinned — click to unpin' : 'Click to pin this tab (protects it from Close Other Tabs / Close Tabs to the Right)'}">${tab.pinned ? '📌' : '📍'}</span><span class="lock" title="${tab.locked ? 'Locked — click to release' : 'Click to lock this tab against Iter'}">${tab.locked ? '🔒' : '🔓'}</span><span class="title">${escapeHtml(tab.title || 'New Tab')}</span><span class="x">✕</span>`;
    pill.querySelector('.title').addEventListener('click', () => window.iterApi.switchTab(tab.id));
    pill.querySelector('.pin').addEventListener('click', (e) => {
      e.stopPropagation();
      window.iterApi.togglePinTab(tab.id);
    });
    pill.querySelector('.lock').addEventListener('click', (e) => {
      e.stopPropagation();
      window.iterApi.toggleLockTab(tab.id);
    });
    pill.querySelector('.x').addEventListener('click', (e) => {
      e.stopPropagation();
      if (tab.locked) return; // must release the lock first
      window.iterApi.closeTab(tab.id);
    });
    pill.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      window.iterApi.showTabContextMenu(tab.id);
    });
    pill.addEventListener('dragstart', (e) => {
      dragTabId = tab.id;
      e.dataTransfer.effectAllowed = 'move';
      pill.classList.add('dragging');
    });
    pill.addEventListener('dragend', () => pill.classList.remove('dragging'));
    pill.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (dragTabId != null && dragTabId !== tab.id) pill.classList.add('drag-over');
    });
    pill.addEventListener('dragleave', () => pill.classList.remove('drag-over'));
    pill.addEventListener('drop', (e) => {
      e.preventDefault();
      pill.classList.remove('drag-over');
      if (dragTabId == null || dragTabId === tab.id) return;
      const ids = tabsCache.map((t) => t.id);
      const from = ids.indexOf(dragTabId);
      const to = ids.indexOf(tab.id);
      if (from === -1 || to === -1) return;
      ids.splice(to, 0, ids.splice(from, 1)[0]);
      window.iterApi.reorderTabs(ids);
      dragTabId = null;
    });
    tabstripScroll.appendChild(pill);
  }
  renderAllTabsMenu(list);
  scheduleHeightReport();
}

// "tabs ▾" -- kept as a quick jump-list even though wrapping means every
// tab is now visible in the strip itself; still handy for jumping straight
// to a tab without hunting across rows once there are many.
function renderAllTabsMenu(list) {
  tabAllBtn.textContent = `${list.length} tab${list.length === 1 ? '' : 's'} \u25be`;
  tabAllMenu.innerHTML = '';
  for (const tab of list) {
    const row = document.createElement('div');
    row.className = 'row-item' + (tab.active ? ' active' : '');
    row.title = tab.url;
    row.innerHTML = `<span class="title">${tab.pinned ? '📌 ' : ''}${tab.locked ? '🔒 ' : ''}${escapeHtml(tab.title || 'New Tab')}</span><span class="x">✕</span>`;
    row.querySelector('.title').addEventListener('click', () => {
      window.iterApi.switchTab(tab.id);
      tabAllMenu.hidden = true;
    });
    row.querySelector('.x').addEventListener('click', (e) => {
      e.stopPropagation();
      if (tab.locked) return;
      window.iterApi.closeTab(tab.id);
    });
    tabAllMenu.appendChild(row);
  }
}
tabAllBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  tabAllMenu.hidden = !tabAllMenu.hidden;
});
document.addEventListener('click', (e) => {
  if (!tabAllMenu.hidden && !tabAllMenu.contains(e.target) && e.target !== tabAllBtn) {
    tabAllMenu.hidden = true;
  }
});
document.getElementById('tab-new').addEventListener('click', () => window.iterApi.newTab('https://www.google.com'));

window.iterApi.onTabsUpdate(renderTabs);
window.iterApi.listTabs().then(renderTabs);

// ---------------------------------------------------------------------
// Height reporting -- tells main.js how tall this strip actually rendered
// (1 row vs. 2 vs. 3...) so it can grow/shrink the view and push the
// sidebar/toolbar/page down (or back up) to match. Debounced with a
// rAF + last-value check so a burst of DOM churn (e.g. re-rendering all
// pills on every tabs:update) reports once, not repeatedly, and a resize
// that doesn't actually change the row count is a no-op.
// ---------------------------------------------------------------------
let lastReportedHeight = 0;
let reportScheduled = false;
function scheduleHeightReport() {
  if (reportScheduled) return;
  reportScheduled = true;
  requestAnimationFrame(() => {
    reportScheduled = false;
    const h = Math.ceil(tabstripEl.getBoundingClientRect().height);
    if (h > 0 && h !== lastReportedHeight) {
      lastReportedHeight = h;
      window.iterApi.reportTabstripHeight(h);
    }
  });
}
new ResizeObserver(scheduleHeightReport).observe(tabstripEl);
scheduleHeightReport();
