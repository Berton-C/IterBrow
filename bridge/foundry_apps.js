// Fixed browser-observation grammar. Caller strings are data, never executable
// expressions. These raw observations are evidence, not completion/authorization.
const { probeScript } = require('./page_scripts');

// A probe of any app (M13-C4): the app, 1–30 assertions, at most 30 click/fill steps, a clamped timeout.
function validateProbeSpec(params) {
  if (!params || !/^[a-z][a-z0-9-]{0,62}$/.test(params.appId || '')) throw new Error('Invalid appId');
  const steps = params.steps || [];
  const assertions = params.assertions || [];
  if (!Array.isArray(steps) || steps.length > 30 || !Array.isArray(assertions) || assertions.length < 1 || assertions.length > 30) {
    throw new Error('Probe requires 1–30 assertions and at most 30 interactions');
  }
  const check = (item, kinds) => {
    if (!item || !kinds.includes(item.kind) || typeof item.selector !== 'string'
      || !item.selector.trim() || item.selector.length > 512) throw new Error('Invalid probe step');
  };
  steps.forEach((step) => {
    check(step, ['click', 'fill']);
    if (step.kind === 'fill' && (typeof step.value !== 'string' || step.value.length > 8192)) throw new Error('Invalid fill value');
  });
  assertions.forEach((item) => {
    check(item, ['text', 'value', 'count', 'visible']);
    const type = { text: 'string', value: 'string', count: 'number', visible: 'boolean' }[item.kind];
    if (typeof item.expected !== type || (type === 'number' && (!Number.isInteger(item.expected) || item.expected < 0))) {
      throw new Error('Assertion expected value has wrong type');
    }
    if (type === 'string' && item.expected.length > 8192) throw new Error('Assertion expected value is too large');
  });
  return { appId: params.appId, steps, assertions,
    timeoutMs: Math.min(10000, Math.max(100, Number(params.timeoutMs) || 3000)) };
}

// The revisioned probe (inspectApp): the same spec plus the exact app revision it observes.
function validateProbe(params) {
  if (!params || !/^[a-z][a-z0-9-]{0,62}$/.test(params.appId || '')) throw new Error('Invalid appId');
  if (!/^apprev-[a-f0-9]{64}$/.test(params.revisionId || '')) throw new Error('Exact revisionId required');
  const spec = validateProbeSpec(params);
  return { appId: spec.appId, revisionId: params.revisionId, steps: spec.steps, assertions: spec.assertions,
    timeoutMs: spec.timeoutMs };
}

function probeProofs(facts, spec) {
  const observed = facts && facts.observations;
  const matches = Array.isArray(observed) && observed.length === spec.assertions.length
    && observed.every((item, index) => (
      item.kind === spec.assertions[index].kind && item.selector === spec.assertions[index].selector
      && item.actual === spec.assertions[index].expected
    ));
  return { 'browser-workflow': matches && facts.ready === true ? 'passed' : 'failed' };
}

module.exports = { validateProbe, validateProbeSpec, probeScript, probeProofs };
