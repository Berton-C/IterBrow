// Bookmarks (docs/milestones/M11_browser_track.md section B1). Pure list functions: main.js owns the
// file (.runtime/bookmarks.json) and the menu; these never touch disk. A bookmark is
// {url, title, addedAt}; the list is newest first and unique by normalized URL.
'use strict';

function normalizeUrl(url) {
  const value = String(url == null ? '' : url).trim();
  const hash = value.indexOf('#');
  return hash >= 0 ? value.slice(0, hash) : value;
}

function bookmarkable(url) {
  return /^(https?|file):/i.test(normalizeUrl(url));
}

function isBookmarked(list, url) {
  const key = normalizeUrl(url);
  return (Array.isArray(list) ? list : []).some((item) => item && normalizeUrl(item.url) === key);
}

function remove(list, url) {
  const key = normalizeUrl(url);
  return (Array.isArray(list) ? list : []).filter((item) => item && normalizeUrl(item.url) !== key);
}

function add(list, { url, title, at } = {}) {
  if (!bookmarkable(url)) return list;
  const key = normalizeUrl(url);
  const entry = { url: key, title: String(title || '').trim() || key, addedAt: Number.isFinite(Number(at)) ? Number(at) : Date.now() };
  return [entry, ...remove(list, key)];
}

function toggle(list, item = {}) {
  if (isBookmarked(list, item.url)) return { list: remove(list, item.url), bookmarked: false };
  const next = add(list, item);
  return { list: next, bookmarked: next !== list };
}

function matches(item, words) {
  const haystack = `${item.title || ''} ${item.url || ''}`.toLowerCase();
  return words.every((word) => haystack.includes(word));
}

function search(list, q, limit = 8) {
  const items = (Array.isArray(list) ? list : []).filter((item) => item && item.url);
  const words = String(q || '').toLowerCase().split(/\s+/).filter(Boolean);
  return (words.length ? items.filter((item) => matches(item, words)) : items).slice(0, limit);
}

module.exports = { normalizeUrl, bookmarkable, isBookmarked, add, remove, toggle, search };
