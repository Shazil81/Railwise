import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';

test('passenger drafts are isolated, copied, expiring, and cleared on logout',async()=>{
 const server=await createServer({cacheDir:'node_modules/.vite-tests-drafts',server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
 try{
  const m=await server.ssrLoadModule('/src/passengerDraft.ts');
  const value={passengers:[{name:'Demo',age:25}],email:'test@example.invalid',phone:'',preferences:{}};
  m.savePassengerDraft('user-a:route',value);
  value.passengers[0].name='Changed';
  assert.equal(m.readPassengerDraft('user-a:route').passengers[0].name,'Demo');
  assert.equal(m.readPassengerDraft('user-b:route'),undefined);
  const now=Date.now;Date.now=()=>now()+31*60*1000;
  try{assert.equal(m.readPassengerDraft('user-a:route'),undefined);}finally{Date.now=now;}
  m.savePassengerDraft('user-a:route',value);m.clearPassengerDrafts();
  assert.equal(m.readPassengerDraft('user-a:route'),undefined);
 }finally{await server.close();}
});

test('payment SDK deduplicates loads and permits retry after failure',async()=>{
 const server=await createServer({cacheDir:'node_modules/.vite-tests-sdk',server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
 const oldWindow=globalThis.window,oldDocument=globalThis.document;
 const scripts=[];
 globalThis.window={};globalThis.document={createElement:()=>({remove(){this.removed=true;}}),head:{append:s=>scripts.push(s)}};
 try{
  const {loadRazorpaySdk}=await server.ssrLoadModule('/src/razorpaySdk.ts');
  const first=loadRazorpaySdk();assert.equal(loadRazorpaySdk(),first);assert.equal(scripts.length,1);
  scripts[0].onerror();await assert.rejects(first,/could not load/);assert.equal(scripts[0].removed,true);
  const retry=loadRazorpaySdk();assert.equal(scripts.length,2);
  window.Razorpay=function(){};scripts[1].onload();await retry;
  await loadRazorpaySdk();assert.equal(scripts.length,2);
 }finally{globalThis.window=oldWindow;globalThis.document=oldDocument;await server.close();}
});

test('page visibility signals pause/resume and remove their subscription on cleanup',async()=>{
 const server=await createServer({cacheDir:'node_modules/.vite-tests-visibility',server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
 const oldDocument=globalThis.document;const listeners=new Set();
 globalThis.document={hidden:false,addEventListener:(type,fn)=>{assert.equal(type,'visibilitychange');listeners.add(fn);},removeEventListener:(type,fn)=>listeners.delete(fn)};
 try{
  const {subscribeVisibility,pageIsVisible}=await server.ssrLoadModule('/src/usePageVisibility.ts');
  const seen=[];const cleanup=subscribeVisibility(()=>seen.push(pageIsVisible()));
  assert.equal(pageIsVisible(),true);
  document.hidden=true;for(const fn of listeners)fn();
  document.hidden=false;for(const fn of listeners)fn();
  assert.deepEqual(seen,[false,true]);cleanup();assert.equal(listeners.size,0);
 }finally{globalThis.document=oldDocument;await server.close();}
});
