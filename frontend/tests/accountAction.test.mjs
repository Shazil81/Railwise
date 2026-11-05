import test from 'node:test';
import assert from 'node:assert/strict';
import { readAccountAction } from '../src/accountAction.ts';

function location(hash) {
  const calls=[];
  globalThis.window={location:{hash,pathname:'/',search:'?view=trains'},history:{replaceState: (...args)=>calls.push(args)}};
  return calls;
}

test('verification fragment is captured then removed without losing ordinary search parameters',()=>{
  const calls=location('#account_action=verify&token=secret-link-token');
  assert.deepEqual(readAccountAction(),{purpose:'verify',token:'secret-link-token'});
  assert.equal(calls[0][2],'/?view=trains');
});
test('reset fragment selects reset mode',()=>{
  location('#account_action=reset&token=reset-token');
  assert.deepEqual(readAccountAction(),{purpose:'reset',token:'reset-token'});
});
test('ordinary navigation does not become account recovery',()=>{
  const calls=location('#bookings');
  assert.equal(readAccountAction(),null);
  assert.equal(calls.length,0);
});
test('missing tokens and unknown actions do not open recovery',()=>{
  for(const hash of ['#account_action=verify','#account_action=reset&token=','#account_action=delete&token=x']) {
    const calls=location(hash);
    assert.equal(readAccountAction(),null);
    assert.equal(calls.length,0);
  }
});
