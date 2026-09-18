// Full-width navigation toolbar — lives in its own WebContentsView, sitting
// above the actual browsed-page view, so back/forward/reload/address bar
// behave like a normal browser instead of being buried in the sidebar.
const btnBack = document.getElementById('btn-back');
const btnForward = document.getElementById('btn-forward');
const btnReload = document.getElementById('btn-reload');
const addr = document.getElementById('addr');
const lockIndicator = document.getElementById('lock-indicator');

let activeTabId = null;
let addrFocused = false;

addr.addEventListener('focus', () => { addrFocused = true; });
addr.addEventListener('blur', () => { addrFocused = false; });

function renderFromTabs(list) {
  const active = list.find((t) => t.active);
  activeTabId = active ? active.id : null;
  // Don't stomp on text the user is actively typing/selecting.
  if (active && !addrFocused) addr.value = active.url;
  btnBack.disabled = !active || !active.canGoBack;
  btnForward.disabled = !active || !active.canGoForward;
  lockIndicator.classList.toggle('visible', !!(active && active.locked));
  lockIndicator.title = active && active.locked
    ? 'This tab is locked — Iter cannot alter or close it until you click the lock in the tab strip.'
    : '';
}

window.iterApi.onTabsUpdate(renderFromTabs);
window.iterApi.listTabs().then(renderFromTabs);

btnBack.addEventListener('click', () => activeTabId && window.iterApi.back(activeTabId));
btnForward.addEventListener('click', () => activeTabId && window.iterApi.forward(activeTabId));
btnReload.addEventListener('click', () => activeTabId && window.iterApi.reload(activeTabId));
document.getElementById('btn-go').addEventListener('click', go);
document.getElementById('btn-dashboards').addEventListener('click', () => window.iterApi.openDashboards());
document.getElementById('btn-pwq').addEventListener('click', () => window.iterApi.openPWQ());
document.getElementById('btn-crm').addEventListener('click', () => window.iterApi.openCRM());
addr.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });

function go() {
  if (!activeTabId) return;
  let url = addr.value.trim();
  if (!/^[a-z]+:\/\//i.test(url)) {
    url = url.includes('.') && !url.includes(' ') ? 'https://' + url : 'https://www.google.com/search?q=' + encodeURIComponent(url);
  }
  window.iterApi.navigate(activeTabId, url);
  addr.blur();
}
