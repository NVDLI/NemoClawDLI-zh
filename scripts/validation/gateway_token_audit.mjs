#!/usr/bin/env node
import fs from 'node:fs';

const PATHS = {
  helper: 'web/nemoclaw/scripts/_openclaw.js',
  shared: 'web/nemoclaw/scripts/_shared.js',
  runtime: 'scripts/runtime/test_page_runtime.js',
  en: 'web/nemoclaw/03a-kickstart.html',
  pt: 'i18n/pt/web/nemoclaw/03a-kickstart.html',
  es: 'i18n/es/web/nemoclaw/03a-kickstart.html',
};

function readAll(overrides = {}) {
  return Object.fromEntries(Object.entries(PATHS).map(([key, file]) => [
    key, Object.hasOwn(overrides, key) ? overrides[key] : fs.readFileSync(file, 'utf8'),
  ]));
}

function functionSource(source, declaration) {
  const start = source.indexOf(declaration);
  if (start < 0) return null;
  const brace = source.indexOf('{', start);
  if (brace < 0) return null;
  let depth = 0;
  for (let i = brace; i < source.length; i++) {
    if (source[i] === '{') depth++;
    if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  return null;
}

function compile(source, declaration) {
  const found = functionSource(source, declaration);
  if (!found) return null;
  return Function(`return (${found.replace(/^export\s+/, '')})`)();
}

function parserFindings(label, parser) {
  if (!parser) return [`${label}: token parser is missing`];
  const urlSafe = 'AbCd_ef-0123456789.uvwxyz~token';
  const cases = [
    ['fragment', `/#token=${urlSafe}`, urlSafe],
    ['query', `/?token=${urlSafe}`, urlSafe],
    ['encoded', '/#token=abc%2D_DEF%2E123', 'abc-_DEF.123'],
    ['absent', '/dashboard', null],
  ];
  const out = [];
  for (const [name, value, expected] of cases) {
    const actual = parser(value) || null;
    if (actual !== expected) out.push(`${label}: ${name} token parsed as ${JSON.stringify(actual)}`);
  }
  return out;
}

function audit(overrides = {}) {
  const files = readAll(overrides);
  const findings = [];

  const metadataParser = compile(files.helper, 'export function gatewayTokenFromAgentMetadata');
  findings.push(...parserFindings('course helper', raw => metadataParser?.({ agent: { dashboardUrl: raw } })));

  const runtimeParser = compile(files.runtime, 'function gatewayTokenFromDashboardUrl');
  findings.push(...parserFindings('browser harness', runtimeParser));

  for (const key of ['en', 'pt', 'es']) {
    const source = files[key];
    if (!source.includes('gatewayTokenFromAgentMetadata')) {
      findings.push(`${key}: shared gateway-token parser is not imported`);
    }
    if (!source.includes('autofillToken: gatewayTokenFromAgentMetadata')) {
      findings.push(`${key}: OpenClaw probe does not use the shared gateway-token parser`);
    }
    if (/token=\(\[a-f0-9\]/i.test(source)) {
      findings.push(`${key}: hex-only gateway-token parser returned`);
    }
  }

  if (!files.shared.includes('gatewayTokenFromAgentMetadata')) {
    findings.push('shared runtime does not re-export gatewayTokenFromAgentMetadata');
  }
  if (!files.runtime.includes('openClawHttpUrl')) {
    findings.push('browser harness does not route credentialed Brev HTTP probes through the hosted relay');
  }
  if (!files.runtime.includes('openclaw-cors-proxy.experiments.courses.nvidia.com')) {
    findings.push('browser harness does not name the hosted OpenClaw relay');
  }
  if (!files.runtime.includes("args.includes('--gateway-only')")
      || !files.runtime.includes("method: 'models.list'")) {
    findings.push('browser harness lacks the focused hosted gateway check');
  }
  if (/token=\(\[a-f0-9\]/i.test(files.runtime)) {
    findings.push('browser harness still assumes hexadecimal gateway tokens');
  }
  return findings;
}

function selfTest() {
  const base = readAll();
  const mutations = [
    ['fragment token', { helper: base.helper.replace('fragment.get("token")', 'null') }],
    ['query token', { helper: base.helper.replace('parsed.searchParams.get("token")', 'null') }],
    ['Portuguese wiring', { pt: base.pt.replace('autofillToken: gatewayTokenFromAgentMetadata', 'autofillToken: null') }],
    ['shared export', { shared: base.shared.replaceAll('gatewayTokenFromAgentMetadata', 'removedGatewayTokenParser') }],
    ['harness relay', { runtime: base.runtime.replaceAll('openclaw-cors-proxy.experiments.courses.nvidia.com', 'relay.invalid') }],
    ['focused browser check', { runtime: base.runtime.replace("args.includes('--gateway-only')", 'false') }],
  ];
  const failures = [];
  for (const [label, overrides] of mutations) {
    if (!audit(overrides).length) failures.push(`missed ${label} mutation`);
  }
  return { passed: mutations.length - failures.length, total: mutations.length, failures };
}

if (process.argv.includes('--self-test')) {
  const result = selfTest();
  console.log(`gateway token self-test: ${result.passed}/${result.total} passed`);
  for (const failure of result.failures) console.error(`  FAIL ${failure}`);
  process.exit(result.failures.length ? 1 : 0);
}

const findings = audit();
if (findings.length) {
  console.error(`gateway token audit: FAIL (${findings.length})`);
  for (const finding of findings) console.error(`  ${finding}`);
  process.exit(1);
}
console.log('gateway token audit: ok');
