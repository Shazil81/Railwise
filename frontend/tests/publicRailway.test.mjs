import test from 'node:test';
import assert from 'node:assert/strict';
import api,{login,logout,getStoredUser} from '../src/api.ts';

test('guest searches need no token and only explicit login authenticates private requests',async()=>{
 const previous=api.defaults.adapter;
 const headers=[];
 api.defaults.adapter=async config=>{
  headers.push(config.headers.Authorization);
  return {status:200,statusText:'OK',headers:{},data:config.url==='/token/'?{token:'fixture-token'}:{},config};
 };
 try {
  assert.equal(getStoredUser().token,null);
  await api.get('/stations/search/');
  assert.equal(headers.at(-1),undefined);
  await login('traveller','fixture-password');
  assert.equal(getStoredUser().username,'traveller');
  headers.length=0;
  for(const url of ['/stations/search/','/trains/search/','/journeys/12/quote/','/journeys/12/availability/']) await api.get(url);
  assert.deepEqual(headers,[undefined,undefined,undefined,undefined]);
  await api.get('/bookings/');
  assert.equal(headers.at(-1),'Token fixture-token');
  await logout();
  assert.equal(getStoredUser().token,null);
  await api.get('/bookings/');
  assert.equal(headers.at(-1),undefined);
 } finally {api.defaults.adapter=previous;}
});
