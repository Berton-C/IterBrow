// Fixed browser-observation grammar. Caller strings are data, never executable
// expressions. These raw observations are evidence, not completion/authorization.
function validateProbe(params) {
  if (!params || !/^[a-z][a-z0-9-]{0,62}$/.test(params.appId || '')) throw new Error('Invalid appId');
  if (!/^apprev-[a-f0-9]{64}$/.test(params.revisionId || '')) throw new Error('Exact revisionId required');
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
  return { appId: params.appId, revisionId: params.revisionId, steps, assertions,
    timeoutMs: Math.min(10000, Math.max(100, Number(params.timeoutMs) || 3000)) };
}

function probeScript(spec) {
  return `(${async function runProbe(input) {
    const deadline = Date.now() + input.timeoutMs;
    const observations = [];
    for (const step of input.steps) {
      if (Date.now() >= deadline) throw new Error('Probe deadline exceeded');
      const element = document.querySelector(step.selector);
      if (!element) throw new Error('Interaction target is absent: ' + step.selector);
      if (step.kind === 'click') element.click();
      else {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement)) {
          throw new Error('Fill requires an input, textarea or select');
        }
        element.value = step.value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
      }
      await new Promise((resolve) => setTimeout(resolve, 25));
    }
    // Give asynchronous command/read-back handlers a bounded settling window.
    await new Promise((resolve) => setTimeout(resolve, Math.min(150, Math.max(0, deadline - Date.now()))));
    for (const item of input.assertions) {
      const matches = document.querySelectorAll(item.selector);
      const element = matches[0];
      let actual = null;
      if (item.kind === 'count') actual = matches.length;
      if (item.kind === 'text') actual = element ? String(element.textContent).slice(0, 8192) : null;
      if (item.kind === 'value') actual = element && 'value' in element ? String(element.value).slice(0, 8192) : null;
      if (item.kind === 'visible') {
        const style = element ? getComputedStyle(element) : null;
        actual = !!element && element.getClientRects().length > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      }
      observations.push({ kind: item.kind, selector: item.selector, actual, expected: item.expected });
    }
    return { observations, title: document.title, ready: !!document.body && document.body.dataset.iterReady === 'true' };
  }.toString()})(${JSON.stringify(spec)})`;
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

module.exports = { validateProbe, probeScript, probeProofs };
