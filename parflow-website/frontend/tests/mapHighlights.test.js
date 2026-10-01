import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../src/components/MapComponent.vue',import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*;\r?$/gm,'').replace('export default','globalThis.definition =');
const context={};vm.runInNewContext(source,context);
test('search and clicked basins retain different colors; older clicks reset',()=>{
  const methods=context.definition.methods;
  const state={highlightIds:['search'],clickHighlightId:'neighbor',styleFor:methods.styleFor};
  assert.equal(methods.styleFor.call(state,'search').fillColor,'#e67e22');
  assert.equal(methods.styleFor.call(state,'neighbor').fillColor,'#35a774');
  state.clickHighlightId='other';
  assert.equal(methods.styleFor.call(state,'neighbor').fillOpacity,0);
  assert.equal(methods.styleFor.call(state,'search').fillColor,'#e67e22');
  state.clickHighlightId='search';
  assert.equal(methods.styleFor.call(state,'search').fillColor,'#35a774');
});

test('map starts with terrain selected', () => {
  assert.equal(context.definition.data().mapType, 'terrain');
});
