// Full-width navigation toolbar — lives in its own WebContentsView, sitting
// above the actual browsed-page view, so back/forward/reload/address bar
// behave like a normal browser instead of being buried in the sidebar.
const btnBack = document.getElementById('btn-back');
const btnForward = document.getElementById('btn-forward');
const btnReload = document.getElementById('btn-reload');
const addr = document.getElementById('addr');
const lockIndicator = document.getElementById('lock-indicator');
const btnBookmark = document.getElementById('btn-bookmark'); // M11-B3
const btnReader = document.getElementById('btn-reader'); // M11-D2

let activeTabId = null;
let addrFocused = false;

addr.addEventListener('focus', () => { addrFocused = true; });
addr.addEventListener('blur', () => { addrFocused = false; });

let activeUrl = '';
let activeIsApp = false;

function renderFromTabs(list) {
  const active = list.find((t) => t.active);
  activeTabId = active ? active.id : null;
  activeUrl = active ? String(active.url || '') : '';
  activeIsApp = !!(active && active.app);
  renderPageButtons();
  // Don't stomp on text the user is actively typing/selecting.
  if (active && !addrFocused) addr.value = readerSourceOf(active.url) || active.url;
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
    if (typeof hideHistory === 'function') hideHistory(); // one search bar at a time (M11-C3)
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


// ---- M11-B3: the bookmark star (docs/milestones/M11_browser_track.md B3) ----
// Bookmarking is the person's click, so it works on a locked tab too; the star is disabled only
// where a bookmark can't apply (anything but http(s) and file pages).
function setBookmarked(on) {
  btnBookmark.classList.toggle('on', on);
  btnBookmark.textContent = on ? '\u2605' : '\u2606';
  btnBookmark.title = on ? 'Bookmarked \u2014 click to remove' : 'Bookmark this tab';
  btnBookmark.setAttribute('aria-pressed', on ? 'true' : 'false');
}

// A reader page (M11-D2) is a data: document whose URL ends with #iter-reader=<the page>.
function readerSourceOf(url) {
  const value = String(url || '');
  const at = value.lastIndexOf('#iter-reader=');
  if (!value.startsWith('data:text/html') || at < 0) return null;
  try {
    const source = decodeURIComponent(value.slice(at + '#iter-reader='.length));
    return /^https?:\/\//i.test(source) ? source : null;
  } catch (_) { return null; }
}

// Buttons whose use depends on what the active tab is showing. Locked tabs keep them: these are the
// person's clicks. Disabled only where the action can't apply.
function renderPageButtons() {
  if (btnBookmark) btnBookmark.disabled = !activeTabId || !/^(https?|file):/i.test(activeUrl);
  if (btnReader) btnReader.disabled = !activeTabId || !/^https?:\/\//i.test(activeUrl) || activeIsApp;
}

if (btnBookmark) {
  setBookmarked(false);
  renderPageButtons();
  btnBookmark.addEventListener('click', () => { if (activeTabId) window.iterApi.bookmarkToggle(activeTabId); });
  if (window.iterApi.onBookmarkState) window.iterApi.onBookmarkState((state) => setBookmarked(!!(state && state.bookmarked)));
}


// ---- M11-C3: history search (docs/milestones/M11_browser_track.md C3) ----
// Cmd+Y opens it; typing searches the person's history (debounced); Up/Down move, Enter or a click
// opens the result (focusing a tab already showing it), Escape closes. One search bar at a time.
const historyBar = document.getElementById('history-bar');
const historyText = document.getElementById('history-text');
const historyList = document.getElementById('history-results');
let historyResults = [];
let historyActive = 0;
let historyTimer = null;
let historySeq = 0;

function historyHost(url) {
  try { return new URL(url).host; } catch (_) { return ''; }
}

function reportHistoryOverlay() {
  if (!window.iterApi.toolbarOverlay) return;
  const showing = historyBar.classList.contains('visible') && historyResults.length > 0;
  window.iterApi.toolbarOverlay(showing ? historyList.offsetHeight : 0);
}

function renderHistory() {
  historyList.replaceChildren(...historyResults.map((item, index) => {
    const li = document.createElement('li');
    li.setAttribute('role', 'option');
    li.classList.toggle('active', index === historyActive);
    const title = document.createElement('span');
    title.className = 'title';
    title.textContent = item.title || item.url;
    const host = document.createElement('span');
    host.className = 'host';
    host.textContent = historyHost(item.url);
    li.append(title, host);
    li.addEventListener('mousedown', (event) => event.preventDefault()); // keep focus in the input
    li.addEventListener('click', () => openHistory(item.url));
    return li;
  }));
  historyList.classList.toggle('visible', historyBar.classList.contains('visible') && historyResults.length > 0);
  reportHistoryOverlay();
}

function runHistorySearch() {
  const seq = ++historySeq;
  Promise.resolve(window.iterApi.historySearch(historyText.value)).then((results) => {
    if (seq !== historySeq) return; // a newer search is on its way
    historyResults = Array.isArray(results) ? results.slice(0, 8) : [];
    historyActive = 0;
    renderHistory();
  }).catch(() => {});
}

function hideHistory() {
  if (!historyBar || !historyBar.classList.contains('visible')) return;
  historyBar.classList.remove('visible');
  historyList.classList.remove('visible');
  if (historyTimer) { clearTimeout(historyTimer); historyTimer = null; }
  reportHistoryOverlay();
}

function openHistory(url) {
  if (!url) return;
  window.iterApi.historyOpen(url);
  hideHistory();
}

if (historyBar && window.iterApi.onHistoryOpen) {
  window.iterApi.onHistoryOpen(() => {
    hideFind(true);
    historyBar.classList.add('visible');
    historyText.focus();
    historyText.select();
    if (historyText.value.trim()) runHistorySearch();
    else renderHistory();
  });
  historyText.addEventListener('input', () => {
    if (historyTimer) clearTimeout(historyTimer);
    historyTimer = setTimeout(() => { historyTimer = null; runHistorySearch(); }, 120);
  });
  historyText.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!historyResults.length) return;
      const step = event.key === 'ArrowDown' ? 1 : -1;
      historyActive = (historyActive + step + historyResults.length) % historyResults.length;
      renderHistory();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      const pick = historyResults[historyActive];
      if (pick) openHistory(pick.url);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      hideHistory();
    }
  });
  document.getElementById('history-close').addEventListener('click', hideHistory);
}


// ---- M11-D2: reader mode (docs/milestones/M11_browser_track.md D2) ----
const readerNotice = document.getElementById('reader-notice');
let readerNoticeTimer = null;

if (btnReader) {
  renderPageButtons();
  btnReader.addEventListener('click', () => { if (activeTabId) window.iterApi.readerOpen(activeTabId); });
}
if (readerNotice && window.iterApi.onReaderNotice) {
  window.iterApi.onReaderNotice((notice) => {
    readerNotice.textContent = String((notice && notice.text) || '');
    readerNotice.classList.add('visible');
    if (readerNoticeTimer) clearTimeout(readerNoticeTimer);
    readerNoticeTimer = setTimeout(() => { readerNotice.classList.remove('visible'); readerNoticeTimer = null; }, 4000);
  });
}
