const test = require('node:test');
const assert = require('node:assert/strict');

const { buildTaskAppendix } = require('../../.github/scripts/keepalive_loop.js');

test('buildTaskAppendix ignores placeholder checklist items for suggested task selection', () => {
  const sections = {
    scope: '_Scope section missing from source issue._',
    tasks: ['- [x] Ship feature', '- [ ] ---', '- [ ] _Filed from the 2026-05-29 design-vs-implementation + blueprint review (upgraded issue set)._'].join('\n'),
    acceptance: '- [ ] Validate released output',
  };
  const checkboxCounts = { total: 2, checked: 1, unchecked: 1 };

  const appendix = buildTaskAppendix(sections, checkboxCounts, {});

  assert.doesNotMatch(appendix, /### Suggested Next Task/);
  assert.doesNotMatch(appendix, /- Validate released output/);
  assert.doesNotMatch(appendix, /- ---/);
  assert.doesNotMatch(appendix, /- _Filed from the/);
});

test('buildTaskAppendix progress excludes placeholder unchecked task items', () => {
  const sections = {
    scope: '_Scope section missing from source issue._',
    tasks: ['- [x] Ship feature', '- [ ] ---', '- [ ] _Filed from the 2026-05-29 design-vs-implementation + blueprint review (upgraded issue set)._'].join('\n'),
    acceptance: '- [ ] Validate released output',
  };
  const checkboxCounts = { total: 12, checked: 9, unchecked: 3 };

  const appendix = buildTaskAppendix(sections, checkboxCounts, {});

  assert.match(appendix, /\*\*Progress:\*\* 1\/1 tasks complete, 0 remaining/);
});
