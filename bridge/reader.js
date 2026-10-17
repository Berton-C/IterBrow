// Reader mode and picture-in-picture (docs/milestones/M11_browser_track.md section D).
//
// READER_SCRIPT and PIP_SCRIPT are page JavaScript that main.js runs in the active tab on the
// person's click (executeJavaScript); everything else here is pure. A reader page is a data: document
// in the same tab, so Back returns to the page; its URL carries the original after
// `#iter-reader=` so the address bar, session restore and Recently Closed can show the real page.
'use strict';

// Runs in the page. Picks the article, clones it, strips everything live from the clone, and returns
// {title, html, textLength, byline}; {title, html: '', textLength: 0, byline: ''} when no block has
// 400 characters of text. Never touches the live page.
const READER_SCRIPT = `(() => {
  const MIN = 400;
  const textOf = (el) => (el.textContent || '').replace(/\\s+/g, ' ').trim();
  const firstH1 = document.querySelector('h1');
  const title = (document.title || '').trim() || (firstH1 ? textOf(firstH1) : '');
  let pick = document.querySelector('article') || document.querySelector('main') || document.querySelector('[role=main]');
  if (!pick || textOf(pick).length < MIN) {
    let best = null;
    let bestScore = 0;
    for (const el of document.querySelectorAll('div, section, td')) {
      const length = textOf(el).length;
      if (length < MIN) continue;
      let linkLength = 0;
      for (const a of el.querySelectorAll('a')) linkLength += textOf(a).length;
      const score = length * (1 - Math.min(1, linkLength / length));
      // Prefer the deeper block when a wrapper scores about the same as the block inside it.
      if (score > bestScore || (best && best.contains(el) && score >= bestScore * 0.9)) {
        best = el;
        bestScore = score;
      }
    }
    pick = best;
  }
  if (!pick || textOf(pick).length < MIN) return { title, html: '', textLength: 0, byline: '' };
  const bylineEl = document.querySelector('[rel=author], .byline, [itemprop=author]');
  const byline = bylineEl ? textOf(bylineEl).slice(0, 200) : '';
  const clone = pick.cloneNode(true);
  clone.querySelectorAll('script, style, link, meta, iframe, object, embed, nav, aside, footer, form, button, input, select, textarea, svg, canvas, noscript, template, frame, frameset, base')
    .forEach((el) => el.remove());
  if (byline) {
    for (const el of clone.querySelectorAll('[rel=author], .byline, [itemprop=author]')) {
      if (textOf(el) === byline) { el.remove(); break; }
    }
  }
  const lead = clone.querySelector('h1');
  if (lead && title && title.startsWith(textOf(lead))) lead.remove();
  const http = (value) => /^https?:\\/\\//i.test(String(value || '').trim());
  for (const el of [clone, ...clone.querySelectorAll('*')]) {
    const tag = el.tagName.toLowerCase();
    for (const attr of [...el.attributes]) {
      const name = attr.name.toLowerCase();
      const keep = (tag === 'a' && name === 'href' && http(attr.value))
        || (tag === 'img' && name === 'src' && http(attr.value))
        || (tag === 'img' && name === 'alt');
      if (!keep) el.removeAttribute(attr.name);
    }
  }
  return { title, html: clone.innerHTML.trim(), textLength: textOf(clone).length, byline };
})()`;

// Runs in the page with a user gesture. The largest video (a playing one first) goes into
// picture-in-picture, or leaves it if one is already there. Returns {ok, reason}.
const PIP_SCRIPT = `(async () => {
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture();
      return { ok: true, reason: 'exited' };
    }
    const area = (v) => { const r = v.getBoundingClientRect(); return Math.max(0, r.width) * Math.max(0, r.height); };
    const playing = (v) => !v.paused && !v.ended && v.readyState > 2;
    const videos = [...document.querySelectorAll('video')].filter((v) => area(v) > 0);
    if (!videos.length) return { ok: false, reason: 'no-video' };
    videos.sort((a, b) => (playing(b) - playing(a)) || (area(b) - area(a)));
    const video = videos[0];
    if (typeof video.requestPictureInPicture !== 'function') return { ok: false, reason: 'unsupported' };
    await video.requestPictureInPicture();
    return { ok: true, reason: 'entered' };
  } catch (err) {
    return { ok: false, reason: (err && err.name) || 'error' };
  }
})()`;

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Belt and braces: the extracted HTML has no scripts, but a page can tamper with what its own DOM
// returns, so the document also refuses every script by CSP and neutralizes any <script it is given.
function inert(html) {
  return String(html || '').replace(/<\s*\/?\s*script/gi, '&lt;script');
}

const READER_STYLE = `
  :root { color-scheme: light dark; --bg: #fbfaf7; --text: #22262a; --muted: #6b7178; --link: #2f5f9e; }
  @media (prefers-color-scheme: dark) { :root { --bg: #17191c; --text: #e4e1da; --muted: #9a9fa6; --link: #8db4e8; } }
  html { background: var(--bg); }
  body { max-width: 68ch; margin: 0 auto; padding: 48px 20px 96px; background: var(--bg); color: var(--text);
    font: 19px/1.6 Charter, "Iowan Old Style", Georgia, "Times New Roman", serif; }
  h1 { font-size: 1.7em; line-height: 1.2; margin: 0 0 .4em; }
  .meta { color: var(--muted); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0 0 2em; }
  .meta a { color: var(--muted); }
  a { color: var(--link); }
  a:not([href]) { color: inherit; text-decoration: none; } /* links whose target was stripped */
  img { max-width: 100%; height: auto; }
  pre, code { font-size: .85em; white-space: pre-wrap; }
  blockquote { margin: 1em 0; padding-left: 1em; border-left: 3px solid var(--muted); color: var(--muted); }
`;

function renderReader({ title, byline, html, url } = {}) {
  const safeTitle = escapeHtml(title);
  const safeUrl = escapeHtml(url);
  let host = '';
  try { host = new URL(String(url)).host; } catch (_) { host = String(url || ''); }
  return `<!doctype html>
<html><head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: http: data:; style-src 'unsafe-inline'">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${safeTitle}</title>
<style>${READER_STYLE}</style>
</head><body>
<h1>${safeTitle}</h1>
<p class="meta">${byline ? `${escapeHtml(byline)} · ` : ''}<a href="${safeUrl}">${escapeHtml(host)}</a></p>
<article>${inert(html)}</article>
</body></html>`;
}

const READER_MARK = '#iter-reader=';

// The original page of a reader URL, or null for any other URL.
function readerSource(url) {
  const value = String(url || '');
  if (!value.startsWith('data:text/html')) return null;
  const at = value.lastIndexOf(READER_MARK);
  if (at < 0) return null;
  try {
    const source = decodeURIComponent(value.slice(at + READER_MARK.length));
    return /^https?:\/\//i.test(source) ? source : null;
  } catch (_) {
    return null;
  }
}

module.exports = { READER_SCRIPT, PIP_SCRIPT, READER_MARK, renderReader, readerSource, escapeHtml };
