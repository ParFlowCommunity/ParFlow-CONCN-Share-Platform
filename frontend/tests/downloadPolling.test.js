import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function fixture(api) {
  const scheduled = [];
  const script = readFileSync(new URL('../src/views/MyDownloads.vue', import.meta.url), 'utf8')
    .split('<script>')[1].split('</script>')[0]
    .replace(/^import .*;\r?\n/gm, '').replace('export default', 'module.exports =');
  const context = { module: { exports: {} }, api, refreshMe: async () => {},
    clearTimeout() {}, setTimeout(fn) { scheduled.push(fn); return scheduled.length; } };
  vm.runInNewContext(script, context);
  const component = context.module.exports;
  const instance = { ...component.data(), $message: { error() {} } };
  for (const [name, fn] of Object.entries(component.methods)) instance[name] = fn.bind(instance);
  return { instance, scheduled };
}
test('silent polling keeps loading mask off and row identity; stops at completed status', async () => {
  let release;
  const { instance, scheduled } = fixture(() => new Promise(resolve => { release = resolve; }));
  const row = { id: 'job1', status: 'running' };
  instance.downloads = [row];
  const pending = instance.loadDownloads(true);
  assert.equal(instance.loading, false);
  release({ items: [{ id: 'job1', status: 'succeeded' }], total: 1 });
  await pending;
  assert.equal(instance.downloads[0], row);
  assert.equal(row.status, 'succeeded');
  assert.equal(scheduled.length, 0);
});
test('active tasks schedule polling; stale page responses cannot replace the new page', async () => {
  const resolvers = [];
  const { instance, scheduled } = fixture(() => new Promise(resolve => resolvers.push(resolve)));
  const oldPage = instance.loadDownloads(true);
  instance.page = 2;
  const newPage = instance.loadDownloads();
  resolvers[1]({ items: [{ id: 'new', status: 'running' }], total: 21 });
  await newPage;
  resolvers[0]({ items: [{ id: 'old', status: 'succeeded' }], total: 1 });
  await oldPage;
  assert.equal(instance.downloads[0].id, 'new');
  assert.equal(instance.total, 21);
  assert.equal(scheduled.length, 1);
});
