// M16-B: the model settings panel's pure module (docs/milestones/M16_shell_from_eaos.md section B; the design
// follows the EAOS Foundry's settings panel, written here for IterBrow's own settings.json).
//
// .runtime/settings.json keeps one entry per provider, so switching providers in the panel loses nothing:
//   { "provider": "openrouter",
//     "openrouter": { "endpoint", "model", "apiKey", "models": [ids last fetched], "pricing": { id: {input, output} } },
//     "openai": { "model", "apiKey", "reasoning" }, "lmstudio": { "endpoint", "model" }, "ollama": {…}, …,
//     …every other setting (vault, keepHistory, sidebarWidth, dock order) untouched }
// Keys never leave the main process: panelState() reports only whether one is stored, and a save with an empty
// key keeps the stored one. Pure: no Electron, no fs; main.js passes `fetchImpl` (Electron's net.fetch).
'use strict';

const PROVIDERS = {
  openrouter: {
    label: 'OpenRouter (cloud, many models)', endpoint: 'https://openrouter.ai/api/v1', key: true,
    note: 'One key for many providers. Fetch models lists them all, with prices; click one, test it, Save & apply.',
  },
  openai: {
    label: 'OpenAI (direct API)', endpoint: 'https://api.openai.com/v1', key: true, reasoning: true,
    note: 'An API key from platform.openai.com with API credit (ChatGPT subscriptions do not include it).',
  },
  lmstudio: {
    label: 'LM Studio (local — works offline)', endpoint: 'http://127.0.0.1:1234/v1', key: false,
    note: 'Load a model in LM Studio and start its server, then Fetch models. Use 127.0.0.1 for offline use.',
  },
  ollama: {
    label: 'Ollama (local)', endpoint: 'http://localhost:11434/v1', key: false,
    note: 'A local Ollama server: no key. Fetch models lists what you have pulled.',
  },
  anthropic: {
    label: 'Anthropic (OpenAI-compatible endpoint)', endpoint: 'https://api.anthropic.com/v1', key: true,
    note: "Anthropic's OpenAI-compatible endpoint with an Anthropic API key; if Fetch models finds nothing, type the model id — Test connection decides.",
  },
  custom: {
    label: 'Custom OpenAI-compatible server', endpoint: '', key: false,
    note: 'Any server that answers POST {endpoint}/chat/completions in the OpenAI shape; a key only if it asks for one.',
  },
};
const PROVIDER_IDS = Object.keys(PROVIDERS);
const REASONING = ['low', 'medium', 'high'];
const LOCAL_KEYS = { lmstudio: 'lm-studio', ollama: 'ollama' };
const FETCH_DEADLINE_MS = 15000;

function entry(settings, provider) {
  const stored = (settings && typeof settings[provider] === 'object' && settings[provider]) || {};
  const preset = PROVIDERS[provider] || PROVIDERS.custom;
  return { ...stored, endpoint: String(provider === 'openai' ? preset.endpoint : (stored.endpoint || preset.endpoint)).trim() };
}

function providerOf(settings) {
  return PROVIDER_IDS.includes(settings && settings.provider) ? settings.provider : 'openrouter';
}

// What Iter's process gets for the chosen provider (startIterProcess). Everything but openai is OpenAI-compatible
// chat completions; LLM_PROVIDER is the provider's name (the loop treats every name but openai as compatible).
function envFor(settings, { openaiModels = null } = {}) {
  const provider = providerOf(settings);
  const preset = PROVIDERS[provider];
  const cfg = entry(settings, provider);
  const key = typeof cfg.apiKey === 'string' ? cfg.apiKey.trim() : '';
  const model = String(cfg.model || '').trim();
  if (provider === 'openai') {
    if (!key) throw new Error('Add your OpenAI API key in Settings before starting Iter.');
    if ((openaiModels && !openaiModels.includes(model)) || !REASONING.includes(cfg.reasoning || 'low')) {
      throw new Error('Choose an available OpenAI model and reasoning effort in Settings.');
    }
  } else if (preset.key && !key) {
    throw new Error(`Add your ${preset.label.split(' (')[0]} API key in Settings before starting Iter.`);
  }
  if (!cfg.endpoint) throw new Error('Set the endpoint for this provider in Settings before starting Iter.');
  if (!model) throw new Error('Choose a model in Settings (Fetch models, then click one) before starting Iter.');
  return {
    BASE_URL: cfg.endpoint,
    LLM_MODEL: model,
    LLM_PROVIDER: provider,
    LLM_REASONING_EFFORT: provider === 'openai' ? (cfg.reasoning || 'low') : '',
    AI_API_KEY: key || LOCAL_KEYS[provider] || 'dummy',
  };
}

// The stored key for a provider unless the form sent a new one (fetch and test run in main with this).
function resolveKey(settings, provider, typed) {
  const fresh = typeof typed === 'string' ? typed.trim() : '';
  if (fresh) return fresh;
  const stored = settings && settings[provider] && settings[provider].apiKey;
  return typeof stored === 'string' ? stored.trim() : '';
}

// Everything the renderer may see: the other settings as they are, and per provider its route without the key.
function panelState(settings) {
  const state = {};
  for (const [name, value] of Object.entries(settings || {})) if (!PROVIDER_IDS.includes(name)) state[name] = value;
  state.provider = providerOf(settings);
  state.providers = {};
  for (const id of PROVIDER_IDS) {
    const cfg = entry(settings, id);
    state.providers[id] = {
      label: PROVIDERS[id].label, note: PROVIDERS[id].note, needsKey: PROVIDERS[id].key,
      endpoint: cfg.endpoint, model: String(cfg.model || ''), reasoning: id === 'openai' ? (cfg.reasoning || 'low') : null,
      hasKey: typeof cfg.apiKey === 'string' && cfg.apiKey.trim() !== '',
      models: Array.isArray(cfg.models) ? cfg.models : [], pricing: cfg.pricing && typeof cfg.pricing === 'object' ? cfg.pricing : null,
    };
  }
  return state;
}

// A save from the panel: the chosen provider and any provider entries it carries, merged onto what is stored.
// An empty key keeps the stored key; models/pricing are kept unless new ones come; nothing else changes.
function applyProvider(stored, change) {
  const next = { ...(stored || {}) };
  if (change && PROVIDER_IDS.includes(change.provider)) next.provider = change.provider;
  for (const id of PROVIDER_IDS) {
    const incoming = change && change[id];
    if (!incoming || typeof incoming !== 'object') continue;
    const before = (next[id] && typeof next[id] === 'object') ? next[id] : {};
    const merged = { ...before };
    if (typeof incoming.endpoint === 'string' && incoming.endpoint.trim()) merged.endpoint = incoming.endpoint.trim();
    if (!merged.endpoint && id !== 'openai') merged.endpoint = PROVIDERS[id].endpoint;
    if (typeof incoming.model === 'string') merged.model = incoming.model.trim();
    if (id === 'openai' && REASONING.includes(incoming.reasoning)) merged.reasoning = incoming.reasoning;
    if (typeof incoming.apiKey === 'string' && incoming.apiKey.trim()) merged.apiKey = incoming.apiKey.trim();
    if (Array.isArray(incoming.models)) merged.models = incoming.models.filter((m) => typeof m === 'string');
    if (incoming.pricing && typeof incoming.pricing === 'object') merged.pricing = incoming.pricing;
    next[id] = merged;
  }
  return next;
}

function base(endpoint) {
  return String(endpoint || '').trim().replace(/\/+$/, '');
}

function headers(key) {
  const out = { 'Content-Type': 'application/json' };
  if (key) out.Authorization = `Bearer ${key}`;
  return out;
}

async function request(fetchImpl, url, init) {
  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), FETCH_DEADLINE_MS) : null;
  try {
    const response = await fetchImpl(url, { ...init, signal: controller ? controller.signal : undefined });
    const text = await response.text();
    let json = null;
    try { json = JSON.parse(text); } catch (_) { json = null; }
    return { ok: response.ok, status: response.status, statusText: response.statusText || '', text, json };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

// OpenRouter's /models carries USD per token as strings; the panel shows USD per 1M tokens.
function perMillion(value) {
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? Number((n * 1e6).toPrecision(6)) : null;
}

// GET {endpoint}/models with the bearer key. Never throws.
async function fetchModels(endpoint, key, fetchImpl) {
  const fail = (status, error) => ({ ok: false, status, models: [], pricing: null, error });
  if (typeof fetchImpl !== 'function') return fail(0, 'fetch is not available here');
  const root = base(endpoint);
  if (!/^https?:\/\/\S+$/i.test(root)) return fail(0, 'The endpoint must be an http(s) URL, e.g. https://openrouter.ai/api/v1');
  try {
    const answer = await request(fetchImpl, `${root}/models`, { method: 'GET', headers: headers(key) });
    if (!answer.ok) return fail(answer.status, `HTTP ${answer.status} ${answer.statusText}: ${answer.text.slice(0, 200).replace(/\s+/g, ' ')}`.trim());
    const list = Array.isArray(answer.json) ? answer.json
      : answer.json && Array.isArray(answer.json.data) ? answer.json.data
        : answer.json && Array.isArray(answer.json.models) ? answer.json.models : null;
    if (!list) return fail(answer.status, 'the answer was not a model list');
    const models = [...new Set(list.map((m) => (typeof m === 'string' ? m : m && (m.id || m.name))).filter((id) => typeof id === 'string' && id))].sort();
    const pricing = {};
    for (const m of list) {
      if (!m || typeof m !== 'object' || !m.pricing) continue;
      const input = perMillion(m.pricing.prompt);
      const output = perMillion(m.pricing.completion);
      if (input !== null && output !== null) pricing[m.id] = { input, output };
    }
    return { ok: true, status: answer.status, models, pricing: Object.keys(pricing).length ? pricing : null, error: null };
  } catch (error) {
    return fail(0, error && error.name === 'AbortError' ? 'no answer within 15 s' : String((error && error.message) || error));
  }
}

const UNSUPPORTED = /^Unsupported (parameter|value)\b/i;

function refusedParameter(json) {
  const err = json && json.error;
  if (!err || typeof err !== 'object') return null;
  const param = typeof err.param === 'string' ? err.param : null;
  if (param && (err.code === 'unsupported_parameter' || err.code === 'unsupported_value' || UNSUPPORTED.test(String(err.message || '')))) return param;
  return null;
}

// One real chat round trip to the named model (a short user message). A parameter the model refuses (max_tokens,
// temperature) is dropped and the ping retried once; `dropped` names it. Never throws.
async function chatPing({ endpoint, key, model, reasoning }, fetchImpl) {
  const body = { model, messages: [{ role: 'user', content: 'Say hello in five words.' }], max_tokens: 32 };
  if (REASONING.includes(reasoning)) body.reasoning_effort = reasoning;
  const dropped = [];
  const started = Date.now();
  try {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const answer = await request(fetchImpl, `${base(endpoint)}/chat/completions`, { method: 'POST', headers: headers(key), body: JSON.stringify(body) });
      const ms = Date.now() - started;
      if (answer.ok) {
        const choice = answer.json && Array.isArray(answer.json.choices) ? answer.json.choices[0] : null;
        const reply = choice && choice.message && typeof choice.message.content === 'string' ? choice.message.content.trim() : '';
        return { ok: true, ms, reply, dropped };
      }
      const param = refusedParameter(answer.json);
      if (attempt === 0 && param && Object.prototype.hasOwnProperty.call(body, param)) {
        delete body[param];
        dropped.push(param);
        continue;
      }
      const message = answer.json && answer.json.error ? (answer.json.error.message || JSON.stringify(answer.json.error)) : answer.text;
      return { ok: false, ms, reply: null, dropped, error: `HTTP ${answer.status}: ${String(message).slice(0, 200).replace(/\s+/g, ' ')}` };
    }
  } catch (error) {
    return { ok: false, ms: Date.now() - started, reply: null, dropped, error: String((error && error.message) || error) };
  }
  return { ok: false, ms: Date.now() - started, reply: null, dropped, error: 'no answer' };
}

// What Test connection reports: the model list and, when a model is named, the chat ping (whose verdict decides).
async function testConnection({ endpoint, key, model, reasoning } = {}, fetchImpl) {
  const name = String(model || '').trim();
  const models = await fetchModels(endpoint, key, fetchImpl);
  const chat = name && typeof fetchImpl === 'function' && /^https?:\/\//i.test(base(endpoint))
    ? await chatPing({ endpoint, key, model: name, reasoning }, fetchImpl) : null;
  const ok = chat ? chat.ok : models.ok;
  const modelsPart = models.ok
    ? `models: ${models.models.length} listed${models.pricing ? ` (${Object.keys(models.pricing).length} with prices)` : ''}`
    : `models: ${models.error}`;
  let chatPart = 'chat: no model named';
  if (chat && chat.ok) {
    const reply = chat.reply.length > 60 ? chat.reply.slice(0, 57) + '…' : chat.reply;
    chatPart = `chat: answered in ${(chat.ms / 1000).toFixed(1)} s ("${reply}")${chat.dropped.length ? ` after dropping ${chat.dropped.join(', ')}` : ''}`;
  } else if (chat) {
    chatPart = `chat: ${chat.error}`;
  }
  return { ok, text: `${ok ? 'ok — ' : ''}${modelsPart} · ${chatPart}`, models,
    reply: chat && chat.ok ? chat.reply : null, ms: chat ? chat.ms : null, dropped: chat ? chat.dropped : [] };
}

module.exports = { PROVIDERS, PROVIDER_IDS, envFor, resolveKey, panelState, applyProvider, fetchModels, testConnection };
