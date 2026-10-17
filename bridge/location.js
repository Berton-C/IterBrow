// Native location for Map Station (docs/milestones/M11_browser_track.md section A1). Pure functions
// only: main.js decides when to run the helper (only for the Map Station page, only on its request)
// and these decide which helper, how to read its output, and how to name a failure.
//
// Why native: Electron's navigator.geolocation goes through Google's network location service and
// needs a billed GOOGLE_API_KEY; without one it fails with Chromium's error 2 whatever macOS says.
'use strict';

const path = require('path');

function inRange(value, limit) {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= limit;
}

function parseTime(value) {
  if (value === undefined || value === null || value === '') return null;
  let date;
  if (typeof value === 'number' && Number.isFinite(value)) {
    date = new Date(value < 1e12 ? value * 1000 : value); // epoch seconds or milliseconds
  } else if (typeof value === 'string') {
    date = /^\d+(\.\d+)?$/.test(value.trim()) ? parseTime(Number(value)) : new Date(value);
    if (typeof date === 'string' || date === null) return date;
  } else {
    return null;
  }
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

// The first JSON object in `text` (CoreLocationCLI may print a leading line).
function firstObject(text) {
  const start = text.indexOf('{');
  if (start < 0) return null;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < text.length; i += 1) {
    const ch = text[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
    } else if (ch === '"') {
      inString = true;
    } else if (ch === '{') {
      depth += 1;
    } else if (ch === '}') {
      depth -= 1;
      if (depth === 0) {
        try { return JSON.parse(text.slice(start, i + 1)); } catch (_) { return null; }
      }
    }
  }
  return null;
}

function parseLocation(text) {
  if (typeof text !== 'string' || !text) return null;
  const obj = firstObject(text);
  if (!obj || typeof obj !== 'object') return null;
  const lat = obj.latitude;
  const lon = obj.longitude;
  if (!inRange(lat, 90) || !inRange(lon, 180)) return null;
  const rawAccuracy = [obj.h_accuracy, obj.horizontalAccuracy, obj.accuracy].find((v) => v !== undefined);
  const accuracy = typeof rawAccuracy === 'number' && Number.isFinite(rawAccuracy) ? rawAccuracy : null;
  return { lat, lon, accuracy, at: parseTime(obj.time) };
}

const BREW_PATHS = ['/opt/homebrew/bin/CoreLocationCLI', '/usr/local/bin/CoreLocationCLI'];

function helperCommand({ env = {}, runtimeDir, exists }) {
  const has = typeof exists === 'function' ? exists : () => false;
  const own = env.ITERBROW_LOCATION_HELPER;
  if (own && path.isAbsolute(own) && has(own)) return { file: own, args: [], source: 'env' };
  if (runtimeDir) {
    const built = path.join(runtimeDir, 'bin', 'iter_location');
    if (has(built)) return { file: built, args: [], source: 'built' };
  }
  for (const file of BREW_PATHS) {
    if (has(file)) return { file, args: ['-once', '-json'], source: 'brew' };
  }
  return null;
}

function failure(code, signal, stderr) {
  const text = String(stderr || '').toLowerCase();
  if (/denied|not authorized|kclerrordomain/.test(text)) return 'denied';
  if (signal === 'SIGKILL' || signal === 'SIGTERM') return 'timeout';
  return 'unavailable';
}

module.exports = { parseLocation, helperCommand, failure, BREW_PATHS };
