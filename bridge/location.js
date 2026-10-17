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

function number(value) {
  if (typeof value === 'number') return value;
  if (typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value.trim())) return Number(value);
  return NaN;
}

// A JSON object (the Swift helper, a helper of the person's own, or CoreLocationCLI --json, whose
// numbers are strings) or CoreLocationCLI's plain "lat lon [h_accuracy]" line. The denial and
// timeout messages the CLI prints are text without numbers, so they parse to null.
function parseLocation(text) {
  if (typeof text !== 'string' || !text) return null;
  const obj = firstObject(text);
  let lat; let lon; let rawAccuracy; let rawTime;
  if (obj && typeof obj === 'object') {
    lat = number(obj.latitude);
    lon = number(obj.longitude);
    rawAccuracy = [obj.h_accuracy, obj.horizontalAccuracy, obj.accuracy].find((v) => v !== undefined);
    rawTime = obj.time;
  } else {
    const line = text.split('\n').map((l) => l.trim()).find((l) => /^-?\d+(\.\d+)?\s+-?\d+(\.\d+)?(\s|$)/.test(l));
    if (!line) return null;
    const parts = line.split(/\s+/);
    lat = Number(parts[0]);
    lon = Number(parts[1]);
    rawAccuracy = parts[2];
  }
  if (!inRange(lat, 90) || !inRange(lon, 180)) return null;
  const accuracyNumber = number(rawAccuracy);
  const accuracy = Number.isFinite(accuracyNumber) && accuracyNumber >= 0 ? accuracyNumber : null;
  return { lat, lon, accuracy, at: parseTime(rawTime) };
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
    // One fix, no reverse geocode (--json would look the address up over the network).
    if (has(file)) return { file, args: ['--format', '%latitude %longitude %h_accuracy'], source: 'brew' };
  }
  return null;
}

// CoreLocationCLI prints its denial and timeout messages on stdout (exit 1), so both streams count.
function failure(code, signal, stderr, stdout) {
  const text = `${stderr || ''}\n${stdout || ''}`.toLowerCase();
  if (/denied|not authorized|kclerrordomain|location services are disabled/.test(text)) return 'denied';
  if (signal === 'SIGKILL' || signal === 'SIGTERM' || /timed out/.test(text)) return 'timeout';
  return 'unavailable';
}

module.exports = { parseLocation, helperCommand, failure, BREW_PATHS };
