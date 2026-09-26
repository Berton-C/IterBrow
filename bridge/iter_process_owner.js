// Reconcile only Python Iter loops whose actual cwd is this workspace.
// No PID-only kill: old heartbeat PIDs can be stale or reused. No model calls.
const fs = require('fs');
const { execFile } = require('child_process');
const { promisify } = require('util');
const exec = promisify(execFile);
const options = { timeout: 3000, maxBuffer: 2 * 1024 * 1024, env: { ...process.env, LC_ALL: 'C' } };
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function identity(pid) {
  let stdout;
  try {
    ({ stdout } = await exec('ps', ['-p', String(pid), '-o', 'stat=', '-o', 'lstart=', '-o', 'command='], options));
  } catch (error) {
    if (error.code === 1 && !String(error.stdout || '').trim()) return null;
    throw error;
  }
  const signature = stdout.trim();
  if (!signature || signature.startsWith('Z')) return null;
  // State is volatile; birth time + complete command identify this process.
  return signature.replace(/^\S+\s+/, '');
}

async function cwdOf(pid) {
  if (process.platform === 'linux') return fs.realpathSync(`/proc/${pid}/cwd`);
  const { stdout } = await exec('/usr/sbin/lsof', ['-a', '-p', String(pid), '-d', 'cwd', '-Fn'], options);
  const line = stdout.split('\n').find((value) => value.startsWith('n'));
  if (!line) throw new Error(`Cannot verify cwd of possible Iter process ${pid}`);
  return fs.realpathSync(line.slice(1));
}

async function findIterProcesses(iterDir) {
  const root = fs.realpathSync(iterDir);
  const { stdout } = await exec('ps', ['-axo', 'pid=,stat=,command='], options);
  const matches = [];
  for (const line of stdout.split('\n')) {
    const match = line.trim().match(/^(\d+)\s+(\S+)\s+(.+)$/);
    if (!match || match[2].startsWith('Z')) continue;
    const [, number, , command] = match;
    // Reconcile loop and detached invocation leaders, never the AtomSpace.
    if (!/(?:^|\/)python(?:\d+(?:\.\d+)*)?(?:\s|$)/i.test(command)
        || !/(?:^|\s|\/)iter\.py(?:$|\s+--invoke\s)/.test(command)) continue;
    const pid = Number(number);
    const signature = await identity(pid);
    if (!signature) continue;
    let cwd;
    try { cwd = await cwdOf(pid); }
    catch (error) { if (!await identity(pid)) continue; throw error; }
    if (cwd === root) {
      const worker = /iter\.py\s+--invoke\s/.test(command);
      let group = false;
      if (worker) {
        try {
          const info = await exec('ps', ['-p', String(pid), '-o', 'pgid='], options);
          group = Number(info.stdout.trim()) === pid;
        } catch (error) { if (!await identity(pid)) continue; throw error; }
      }
      matches.push({ pid, signature, group });
    }
  }
  return matches;
}

async function retirePreviousIter(iterDir, log = () => {}) {
  const retired = [];
  for (const owner of await findIterProcesses(iterDir)) {
    const same = async () => await identity(owner.pid) === owner.signature;
    if (!await same()) continue;
    log(`[recovery] stopping surviving Iter process ${owner.pid} from this workspace`);
    // An orphan invocation has no parent to reap its subprocesses. Stop its
    // verified group together before the leader can exit and lose ownership.
    try { process.kill(owner.group ? -owner.pid : owner.pid, owner.group ? 'SIGKILL' : 'SIGTERM'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline && await same()) await pause(100);
    if (await same()) {
      process.kill(owner.group ? -owner.pid : owner.pid, 'SIGKILL');
      const finalDeadline = Date.now() + 2000;
      while (Date.now() < finalDeadline && await same()) await pause(100);
    }
    if (await same()) throw new Error(`Surviving Iter process ${owner.pid} did not exit`);
    retired.push(owner.pid);
  }
  return { retired };
}

module.exports = { findIterProcesses, retirePreviousIter };
