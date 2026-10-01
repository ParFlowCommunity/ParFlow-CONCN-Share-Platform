import test from 'node:test';
import assert from 'node:assert/strict';
import { createSdkLoader } from '../src/components/mapSdkLoader.js';

function fixture() {
  const scripts = [];
  const window = {};
  const document = {
    createElement: () => ({ remove() { this.removed = true; } }),
    head: { appendChild: script => scripts.push(script) },
  };
  return { scripts, window, load: createSdkLoader({ document, window, key: 'test-key' }) };
}

test('concurrent callers wait for the same script and accept late SDK completion', async () => {
  const f = fixture();
  const pending = f.load();
  assert.equal(f.load(), pending);
  assert.equal(f.scripts.length, 1);
  await new Promise(resolve => setImmediate(resolve));
  f.window.T = { Map: class {} };
  f.scripts[0].onload();
  assert.equal(await pending, f.window.T);
  assert.equal(await f.load(), f.window.T);
});

test('network failure is exposed and a user retry creates a fresh request', async () => {
  const f = fixture();
  const first = f.load();
  f.scripts[0].onerror();
  await assert.rejects(first, /加载失败/);
  assert.equal(f.scripts[0].removed, true);
  const retry = f.load();
  assert.equal(f.scripts.length, 2);
  f.window.T = { Map: class {} };
  f.scripts[1].onload();
  assert.equal(await retry, f.window.T);
});

test('a script response without a usable SDK fails explicitly', async () => {
  const f = fixture();
  const pending = f.load();
  f.scripts[0].onload();
  await assert.rejects(pending, /不可用/);
});
