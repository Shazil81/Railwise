import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeInventory,inventorySegments} from '../src/inventory.ts';
const rows=[{id:1,origin_code:'RJPB',destination_code:'HWH',stops:[{code:'RJPB',sequence:2},{code:'HWH',sequence:5}],classes:[{travel_class:'SL',available_seats:12,capacity:12,total:'400.00'}]}];
const update=(count,start=2)=>({journeys:[{id:1,from_seq:start,to_seq:5,classes:[{travel_class:'SL',available_seats:count,capacity:12}]}]});
test('live inventory subscribes to the actual matched terminal segment',()=>{
  assert.deepEqual(inventorySegments(rows),[[1,2,5]]);
});
test('seat count changes without changing fare or mutating the loaded data',()=>{
  const next=mergeInventory(rows,update(11));
  assert.equal(next[0].classes[0].available_seats,11);
  assert.equal(next[0].classes[0].total,'400.00');
  assert.equal(rows[0].classes[0].available_seats,12);
  assert.equal(mergeInventory(rows,update(12)),rows);
});
test('wrong segment and invalid counts cannot overwrite displayed availability',()=>{
  assert.equal(mergeInventory(rows,update(0,1)),rows);
  assert.equal(mergeInventory(rows,update(-1)),rows);
  assert.equal(mergeInventory(rows,update(13)),rows);
});
