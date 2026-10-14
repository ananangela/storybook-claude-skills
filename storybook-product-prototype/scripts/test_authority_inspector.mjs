import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
// Run in the skill source checkout after installing the existing Storybook template dependencies.
// Optional first argument: directory for inspectable SSR HTML artifacts.
const root = fileURLToPath(new URL('../../', import.meta.url));
const require = createRequire(`${root}/design-system-to-storybook/storybook-template/package.json`);
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const original = fs.readFileSync(`${root}/storybook-product-prototype/assets/prototype-inspector/preview.js`, 'utf8');
const code = original.replace(/^import[\s\S]*?;\n/gm, '').replace(/^export const /gm, 'const ');
const context = vm.createContext({ ...React, console, URL, Date, JSON, Set, Map, UPDATE_GLOBALS: 'UPDATE_GLOBALS', addons: {} });
vm.runInContext(`${code}\nglobalThis.testApi = { readPrototypeDataAuthority, PrototypeData };`, context);
const { readPrototypeDataAuthority, PrototypeData } = context.testApi;
const source = { reference: 'docs/api.yaml#/AlertPage', revision: 'abc123', confirmedBy: 'Alerts RD', confirmedOn: '2026-09-14' };
const row = { group: 'rows', values: 'fake', schemaScope: 'ui-model', status: 'proposed', source: null, owner: 'Product team' };
const registry = (fixture = row, contracts = []) => ({ schemaVersion: 1, fixtures: [fixture], contracts });
const markdown = value => `# Data Spec\n\n## Data Authority\n\`\`\`json\n${JSON.stringify(value)}\n\`\`\`\n\n## Data Schemas (JSON Schema)\n\`\`\`json\n{"type":"object"}\n\`\`\`\n`;
const artifacts = process.argv[2];
if (artifacts) fs.mkdirSync(artifacts, { recursive: true });
const cases = [
  ['fake-only', markdown(registry()), true, ['FAKE', 'UI model proposed', 'No real contracts are provided']],
  ['confirmed-ui', markdown(registry({ ...row, status: 'confirmed', source })), true, ['UI model confirmed — no transport authority', 'abc123']],
  ['confirmed-transport', markdown(registry({ ...row, schemaScope: 'transport', status: 'confirmed', source })), true, ['Transport schema confirmed', 'FAKE', 'Alerts RD']],
  ['independent-api', markdown(registry({ ...row, contractId: 'alerts-api' }, [{ id: 'alerts-api', kind: 'api', status: 'confirmed', source, owner: 'Alerts RD' }])), true, ['UI model proposed', 'alerts-api', 'docs/api.yaml#/AlertPage', 'confirmed']],
  ['legacy', '# Data Spec\n\n## Fixture Inventory\nrows', false, ['Data authority unverified', 'FAKE']],
  ['malformed', '## Data Authority\n```json\n{"schemaVersion":\n```', false, ['malformed JSON', 'Data authority unverified']],
  ['unsupported-confirmation', markdown(registry({ ...row, status: 'confirmed' })), false, ['incomplete confirmation evidence', 'Data authority unverified']],
  ['duplicate-group', markdown({ schemaVersion: 1, fixtures: [row, row], contracts: [] }), false, ['duplicate group', 'Data authority unverified']],
  ['unknown-contract', markdown(registry({ ...row, contractId: 'missing' })), false, ['unknown contract id', 'Data authority unverified']],
  ['duplicate-section', markdown(registry()) + markdown(registry()), false, ['exactly one complete JSON block', 'Data authority unverified']],
  ['missing-fake', markdown(registry({ ...row, values: 'real' })), false, ['invalid fields', 'Data authority unverified']],
  ['duplicate-json-key', '## Data Authority\n```json\n{"schemaVersion":2,"schemaVersion":1,"fixtures":[],"contracts":[]}\n```', false, ['duplicate keys', 'Data authority unverified']],
  ['placeholder-owner', markdown(registry({ ...row, owner: '[Team]' })), false, ['invalid fields', 'Data authority unverified']],
  ['unknown-source', markdown(registry({ ...row, status: 'confirmed', source: { ...source, reference: 'unknown' } })), false, ['incomplete confirmation evidence', 'Data authority unverified']],
  ['bad-source-date', markdown(registry({ ...row, status: 'confirmed', source: { ...source, confirmedOn: '2026-02-30' } })), false, ['incomplete confirmation evidence', 'Data authority unverified']],
];
for (const [name, doc, expectedValid, expected] of cases) {
  assert.equal(readPrototypeDataAuthority(doc).valid, expectedValid, name);
  const prototype = { id: 'authority-review', flow: { routes: [] }, docs: { dataSpec: doc }, data: { overview: { status: 'confirmed by obsolete metadata' }, fixtures: { rows: 2 }, apiContracts: [{ method: 'GET', endpoint: '/example' }] } };
  const html = renderToStaticMarkup(React.createElement(PrototypeData, { prototype }));
  for (const phrase of expected) assert.ok(html.includes(phrase), `${name}: missing ${phrase}`);
  assert.ok(html.includes('API Replacement Requirements'), name);
  assert.ok(!html.includes('<dd>confirmed by obsolete metadata</dd>'), name);
  if (!expectedValid) assert.ok(!html.includes('<td>Transport schema confirmed</td>'), name);
  if (artifacts) fs.writeFileSync(`${artifacts}/${name}.html`, html);
}
const exampleBefore = '```md\n## Data Authority\n```\n' + markdown(registry());
assert.equal(readPrototypeDataAuthority(exampleBefore).valid, true, 'heading inside example ignored');
assert.equal(fs.readFileSync(`${root}/design-system-to-storybook/storybook-template/.storybook/prototype-inspector/preview.js`, 'utf8'), original, 'runtime source parity');
console.log(`PASS ${cases.length} actual React server renders + fenced-heading parser + runtime parity${artifacts ? `; artifacts: ${artifacts}` : ''}`);
