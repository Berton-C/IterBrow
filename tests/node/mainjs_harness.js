// Load the REAL main.js under plain node with a stub 'electron' module, so the
// state functions (export / import / reset / restore) can be exercised against
// a throwaway ITER_DIR.  Process lifecycle hooks (Iter, AtomSpace service) are
// replaced by recorders; everything that touches files runs for real.
//
// Usage (from a test): node mainjs_harness.js <repoCopy> <userData> <scenario.js>
// The scenario module receives the exported API and returns a JSON-able result.
const Module = require('module');
const path = require('path');
const fs = require('fs');

function load(repoRoot, userData) {
  const deep = () => new Proxy(function () {}, {
    get: (t, k) => (k === 'then' ? undefined : k === 'isPackaged' ? false
      : k === 'getPath' ? () => userData : k === 'requestSingleInstanceLock' ? () => true
      : k === 'whenReady' ? () => new Promise(() => {}) : deep()),
    apply: () => deep(), construct: () => deep(),
  });
  const origResolve = Module._resolveFilename;
  Module._resolveFilename = function (req, ...rest) {
    if (req === 'electron') return 'electron-stub';
    return origResolve.call(this, req, ...rest);
  };
  require.cache['electron-stub'] = { id: 'electron-stub', filename: 'electron-stub', loaded: true, exports: deep() };
  const file = path.join(repoRoot, 'main.js');
  let src = fs.readFileSync(file, 'utf8');
  src += `
;const __calls = [];
pauseCognition = async (opts) => { __calls.push(['pause', opts]); return { iterWasRunning: false, ...(opts || {}) }; };
resumeCognition = async (state) => { __calls.push(['resume', state && state.shutdownAtomspace]); };
startMettaServer = async () => { __calls.push(['startMetta']); return {}; };
stopMettaServer = async () => { __calls.push(['stopMetta']); };
waitForAtomspaceReady = async () => ({ ready: true });
callAtomspace = async (method) => { __calls.push(['atomspace', method]); return {}; };
saveTabSession = () => {};
loadTabSession = () => null;
pushLog = (line) => { __calls.push(['log', line]); };
module.exports = { ITER_DIR, AUTO_BACKUP_DIR, STATE_MANIFEST, STATE_PATHS, PORTABLE_STATE_PATHS,
  PORTABLE_ARCHIVE_PATHS, restoreFromZipPath, resetState, runCLI, listAutoBackupsSorted,
  writeStateArchive: typeof writeStateArchive === 'function' ? writeStateArchive : undefined, __calls,
  __setWriteStateArchive: (fn) => { if (typeof writeStateArchive === 'function') writeStateArchive = fn; } };`;
  const m = new Module(file, null);
  m.filename = file;
  m.paths = Module._nodeModulePaths(repoRoot);
  m._compile(src, file);
  return m.exports;
}

if (require.main === module) {
  const [repoRoot, userData, scenarioPath] = process.argv.slice(2);
  const api = load(repoRoot, userData);
  const scenario = require(path.resolve(scenarioPath));
  Promise.resolve(scenario(api))
    .then((result) => { process.stdout.write(JSON.stringify({ ok: true, result }) + '\n'); process.exit(0); })
    .catch((error) => { process.stdout.write(JSON.stringify({ ok: false, error: String(error && error.stack || error) }) + '\n'); process.exit(0); });
}

module.exports = { load };
