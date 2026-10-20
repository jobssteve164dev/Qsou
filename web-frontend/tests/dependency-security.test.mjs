import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const micromatch = require('micromatch');
const consumers = ['micromatch', 'chokidar'];
const parsers = consumers.map(name => createRequire(require.resolve(name))('braces'));

test('brace expansion preserves the source globs consumed by Tailwind and file watchers', () => {
  for (const braces of parsers) {
    assert.deepEqual(braces.expand('src/{pages,components}/**/*.{js,tsx}'), [
      'src/pages/**/*.js', 'src/pages/**/*.tsx',
      'src/components/**/*.js', 'src/components/**/*.tsx',
    ]);
  }
  assert.deepEqual(micromatch(
    ['src/pages/index.tsx', 'src/components/Layout.tsx', 'src/styles/globals.css'],
    'src/{pages,components}/**/*.{js,tsx}',
  ), ['src/pages/index.tsx', 'src/components/Layout.tsx']);
});

test('deep brace and parenthesis patterns are rejected before recursive traversal', () => {
  for (const braces of parsers) {
    for (const [open, close] of [['{', '}'], ['(', ')']]) {
      const pattern = open.repeat(4000) + 'a' + close.repeat(4000);
      for (const operation of [braces, braces.expand, braces.parse]) {
        assert.throws(() => operation(pattern), /exceeds max depth/);
      }
    }
  }
});

test('prebuilt ASTs cannot bypass the brace traversal depth protection', () => {
  for (const braces of parsers) {
    for (const operation of [braces.compile, braces.expand, braces.stringify]) {
      let node = { type: 'text', value: 'a' };
      for (let depth = 0; depth < 200; depth++) {
        const parent = { type: 'brace', nodes: [node] };
        node.parent = parent;
        node = parent;
      }
      const ast = { type: 'root', nodes: [node] };
      node.parent = ast;
      assert.throws(() => operation(ast), /exceeds max depth/);
    }
  }
});
