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
// M10-C2: every local app in one menu (main.js builds it from the catalog and opens the pick).
document.getElementById('btn-apps').addEventListener('click', () => window.iterApi.appsMenu());
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


// ---- M9: the browsing ally (docs/milestones/M9_soul_wonder_ally.md C3) ----
// A lock suggestion only ever asks; locking is the person's click. The compass shows only while
// the ally is on, and lights only while an ally card waits for their answer.
const allyNotice = document.getElementById('ally-notice');
const allyText = document.getElementById('ally-text');
const compass = document.getElementById('compass');
let allySuggestion = null;

function hideAllyNotice() {
  allySuggestion = null;
  if (allyNotice) allyNotice.classList.remove('visible');
}

if (allyNotice && window.iterApi.onAllySuggest) {
  window.iterApi.onAllySuggest((payload) => {
    allySuggestion = payload;
    allyText.textContent = `This ${payload.reason} — lock it?`;
    allyNotice.classList.add('visible');
  });
  document.getElementById('ally-lock').addEventListener('click', () => {
    if (allySuggestion) window.iterApi.allyLock(allySuggestion.tab);
    hideAllyNotice();
  });
  document.getElementById('ally-no').addEventListener('click', () => {
    if (allySuggestion) window.iterApi.allyDecline(allySuggestion.host);
    hideAllyNotice();
  });
}

if (compass && window.iterApi.onCompassState) {
  window.iterApi.onCompassState((state) => {
    compass.classList.toggle('on', !!(state && state.on));
    compass.classList.toggle('live', !!(state && state.on && state.live));
    compass.title = state && state.on && state.live ? 'A pair is live — Iter has handed you a choice' : 'Compass';
  });
}


// ---- M9: find-in-page (docs/milestones/M9_soul_wonder_ally.md D1) ----
const findBar = document.getElementById('find-bar');
const findText = document.getElementById('find-text');
const findCount = document.getElementById('find-count');

function hideFind(notify) {
  if (!findBar.classList.contains('visible')) return;
  findBar.classList.remove('visible');
  findCount.textContent = '';
  if (notify) window.iterApi.findClose();
}

if (findBar && window.iterApi.onFindOpen) {
  window.iterApi.onFindOpen(() => {
    findBar.classList.add('visible');
    findText.focus();
    findText.select();
  });
  window.iterApi.onFindResult((result) => {
    const total = Number(result && result.total) || 0;
    findCount.textContent = total ? `${Number(result.active) || 0} of ${total}` : 'no matches';
  });
  if (window.iterApi.onFindClosed) window.iterApi.onFindClosed(() => hideFind(false));
  findText.addEventListener('input', () => window.iterApi.findQuery(findText.value));
  findText.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (event.shiftKey) window.iterApi.findPrev(); else window.iterApi.findNext();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      hideFind(true);
    }
  });
  document.getElementById('find-next').addEventListener('click', () => window.iterApi.findNext());
  document.getElementById('find-prev').addEventListener('click', () => window.iterApi.findPrev());
  document.getElementById('find-close').addEventListener('click', () => hideFind(true));
}
