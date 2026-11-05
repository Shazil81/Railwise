import test from 'node:test';
import assert from 'node:assert/strict';
import {createAuthSession,clearLegacyLogin} from '../src/authSession.ts';

test('a new page starts as guest even after a previous page signed in',()=>{
 const previousPage=createAuthSession();
 previousPage.set('fixture-token','traveller');
 assert.equal(previousPage.read().username,'traveller');
 const freshPage=createAuthSession();
 assert.deepEqual(freshPage.read(),{token:null,username:null});
 previousPage.clear();
 assert.equal(previousPage.read().token,null);
});

test('old persistent login is removed without removing unrelated browser preferences',()=>{
 const values=new Map([['token','old-token'],['username','demo'],['theme','light']]);
 clearLegacyLogin({removeItem:key=>values.delete(key)});
 assert.deepEqual([...values.entries()],[['theme','light']]);
 assert.doesNotThrow(()=>clearLegacyLogin({removeItem:()=>{throw Error('Storage blocked');}}));
});
