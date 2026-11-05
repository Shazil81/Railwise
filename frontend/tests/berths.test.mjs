import test from 'node:test';
import assert from 'node:assert/strict';
import {berthOptions,berthLabels} from '../src/berths.ts';
test('sleeper classes offer all requested berth preferences',()=>{
  assert.deepEqual(berthOptions('SL'),['ANY','LB','MB','UB','SL','SU']);
  assert.deepEqual(berthOptions('3A'),berthOptions('SL'));
  assert.equal(berthLabels.SL,'Side Lower');
});
test('class-specific preferences do not offer nonexistent middle berths or chair berths',()=>{
  assert.deepEqual(berthOptions('2A'),['ANY','LB','UB','SL','SU']);
  assert.deepEqual(berthOptions('1A'),['ANY','LB','UB']);
  assert.deepEqual(berthOptions('CC'),['ANY']);
  assert.deepEqual(berthOptions('EC'),['ANY']);
});
