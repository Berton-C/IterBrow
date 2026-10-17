// The browsing ally (docs/milestones/M9_soul_wonder_ally.md section C1). Pure functions only:
// main.js decides when to call them, and only while the person has `browsing_ally` on.
//
// - suggestLock: a conservative "this looks like your bank / mail / health or government
//   account; lock it?" It only ever asks; locking is the person's click.
// - shouldLog: which tabs may appear in the browsing log at all (never app tabs, never locked
//   tabs, only http(s), only while the feature is on).
// - compassState: whether Iter has handed the person a choice (an ally card) still unanswered.
// - recentBrowsing: the last half hour as domains with dwell minutes, newest first.
'use strict';

const BANK_HOSTS = [
  'chase.com', 'bankofamerica.com', 'wellsfargo.com', 'citi.com', 'citibank.com', 'capitalone.com', 'usbank.com',
  'pnc.com', 'tdbank.com', 'ally.com', 'sofi.com', 'chime.com', 'mercury.com', 'americanexpress.com', 'discover.com',
  'schwab.com', 'fidelity.com', 'vanguard.com', 'etrade.com', 'interactivebrokers.com', 'robinhood.com',
  'paypal.com', 'venmo.com', 'wise.com', 'revolut.com', 'monzo.com', 'coinbase.com', 'kraken.com', 'binance.com',
  'gemini.com', 'hyperliquid.xyz', 'mercadopago.com', 'mercadopago.com.ar',
];
const MAIL_HOSTS = ['mail.google.com', 'outlook.live.com', 'outlook.office.com', 'outlook.office365.com',
  'mail.proton.me', 'mail.yahoo.com', 'app.fastmail.com', 'mail.zoho.com'];
const GOV_WORDS = ['health', 'medicare', 'medicaid', 'irs', 'ssa', 'tax'];

function parse(url) {
  try {
    const parsed = new URL(String(url));
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    const host = parsed.hostname.toLowerCase();
    if (!host || host === 'localhost' || /^127\./.test(host) || host === '[::1]') return null;
    return { host, path: parsed.pathname.toLowerCase() };
  } catch (_) {
    return null;
  }
}

function hostIs(host, domain) {
  return host === domain || host.endsWith('.' + domain);
}

function suggestLock(url, _title) {
  const parsed = parse(url);
  if (!parsed) return null;
  const { host, path } = parsed;
  if (BANK_HOSTS.some((d) => hostIs(host, d)) || /bank(ing)?/.test(host)) return { reason: 'looks like your bank' };
  if (MAIL_HOSTS.some((d) => hostIs(host, d)) || (hostIs(host, 'icloud.com') && path.startsWith('/mail'))) {
    return { reason: 'looks like your mail' };
  }
  const labels = host.split('.');
  if (host.includes('mychart') || host.includes('patient')
      || (labels[labels.length - 1] === 'gov' && labels.some((label) => GOV_WORDS.includes(label)))) {
    return { reason: 'looks like a health or government account' };
  }
  return null;
}

function shouldLog(tab, on) {
  if (!on || !tab || tab.locked || tab.appScope) return false;
  return /^https?:\/\//i.test(String(tab.url || ''));
}

function compassState(history) {
  const open = new Map(); // card id -> pair, in order
  for (const message of Array.isArray(history) ? history : []) {
    if (message && message.role === 'iter' && message.card && typeof message.card.topic === 'string'
        && message.card.topic.startsWith('ally:')) {
      open.set(message.card.id, message.card.topic.slice('ally:'.length));
    } else if (message && message.role === 'user' && message.choice && open.has(message.choice.card)) {
      open.delete(message.choice.card);
    }
  }
  const pairs = [...open.values()];
  return pairs.length ? { live: true, pair: pairs[pairs.length - 1] } : { live: false, pair: null };
}

function recentBrowsing(lines, now, windowMs = 30 * 60 * 1000, limit = 8) {
  const recent = (Array.isArray(lines) ? lines : [])
    .filter((line) => line && Number.isFinite(Number(line.at)) && Number(line.at) >= now - windowMs && line.domain)
    .sort((a, b) => Number(a.at) - Number(b.at));
  const runs = [];
  recent.forEach((line, index) => {
    const end = index + 1 < recent.length ? Number(recent[index + 1].at) : now;
    const dwell = Math.max(0, end - Number(line.at));
    const last = runs[runs.length - 1];
    if (last && last.domain === line.domain) {
      last.ms += dwell;
      last.title = line.title || last.title;
    } else {
      runs.push({ domain: line.domain, ms: dwell, title: line.title || '' });
    }
  });
  return runs.reverse().slice(0, limit).map((run) => ({ domain: run.domain, minutes: Math.round(run.ms / 60000), title: run.title }));
}

module.exports = { suggestLock, shouldLog, compassState, recentBrowsing };
