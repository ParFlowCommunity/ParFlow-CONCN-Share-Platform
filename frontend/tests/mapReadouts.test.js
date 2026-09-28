import test from 'node:test';
import assert from 'node:assert/strict';
import {coordinate,scaleAt} from '../src/utils/mapReadouts.js';
test('map coordinates use hemispheres, five decimals and longitude wrapping',()=>{
  assert.equal(coordinate(116.40769,'lng'),'E116.40769°');
  assert.equal(coordinate(-35.5,'lat'),'S35.50000°');
  assert.equal(coordinate(190,'lng'),'W170.00000°');
  assert.equal(coordinate(null,'lng'),'—');
});
test('scale responds to latitude and zoom without clamping its real pixel width',()=>{
  for(const lat of [0,30,60])for(const zoom of [3,8,18]){
    const s=scaleAt(lat,zoom);assert.ok(s.width>0&&s.width<=120);
    const [value,unit]=s.text.split(' ');const distance=Number(value)*(unit==='km'?1000:1);
    assert.ok(Math.abs(s.width*(156543.033928*Math.cos(lat*Math.PI/180)/2**zoom)-distance)<1e-6);
  }
});
