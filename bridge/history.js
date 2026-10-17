// Browsing history (docs/milestones/M11_browser_track.md section C1). Pure functions: main.js owns
// the file (.runtime/history.jsonl, one {at, url, title} per line) and decides when to call these.
//
// What may be recorded is exactly the browsing ally's rule (browsing_ally.shouldLog): only while the
// person keeps history on, only http(s), never a locked tab, never an app tab. The lock is the
// person's "don't touch" line, and .runtime/ is readable by Iter's file tools.
'use strict';

const { shouldLog } = require('./browsing_ally');

const COALESCE_MS = 5000;

function shouldRecord(tab, on) {
  return shouldLog(tab, on);
}

// A navigation to the same URL within 5 s of the last line replaces it (redirect chains, the
// did-navigate double fire); older lines drop off the front at `cap`.
function append(lines, entry, cap = 5000) {
  const list = Array.isArray(lines) ? lines.slice() : [];
  const line = { at: Number(entry.at), url: String(entry.url || ''), title: String(entry.title || '') };
  const last = list[list.length - 1];
  if (last && last.url === line.url && line.at - Number(last.at) <= COALESCE_MS) list[list.length - 1] = line;
  else list.push(line);
  return list.length > cap ? list.slice(list.length - cap) : list;
}

// Titles arrive after did-navigate: retitle the latest line for `url` only.
function titled(lines, url, title) {
  const list = Array.isArray(lines) ? lines.slice() : [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (list[i] && list[i].url === url) {
      list[i] = { ...list[i], title: String(title || '') };
      break;
    }
  }
  return list;
}

// Newest first, unique by URL (the latest visit's title and time, with the visit count); every word
// of `q` must match the title or the URL, case-insensitively. Empty `q` gives the latest `limit`.
function search(lines, q, limit = 8) {
  const byUrl = new Map();
  for (const line of Array.isArray(lines) ? lines : []) {
    if (!line || !line.url) continue;
    const seen = byUrl.get(line.url);
    if (!seen) {
      byUrl.set(line.url, { url: line.url, title: line.title || '', at: Number(line.at), visits: 1 });
    } else {
      seen.visits += 1;
      if (Number(line.at) >= seen.at) {
        seen.at = Number(line.at);
        seen.title = line.title || seen.title;
      }
    }
  }
  const words = String(q || '').toLowerCase().split(/\s+/).filter(Boolean);
  const results = [...byUrl.values()]
    .filter((item) => {
      const haystack = `${item.title} ${item.url}`.toLowerCase();
      return words.every((word) => haystack.includes(word));
    })
    .sort((a, b) => b.at - a.at);
  return results.slice(0, limit);
}

module.exports = { shouldRecord, append, titled, search, COALESCE_MS };
