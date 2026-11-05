import test from 'node:test';
import assert from 'node:assert/strict';
import { boardingDate } from '../src/bookingDate.ts';

test('passenger page uses boarding day rather than train origin day',()=>{
  assert.equal(boardingDate('2026-10-21',2),'2026-10-22');
  assert.equal(boardingDate('2026-10-22',1),'2026-10-22');
  assert.equal(boardingDate('2026-12-31',3),'2027-01-02');
});
