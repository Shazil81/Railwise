import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveSearchEndpoint } from '../src/search.ts';
import api, { getJourneys } from '../src/api.ts';

const city={stations:[{code:'PNBE',name:'Patna Jn'},{code:'RJPB',name:'Rajendra Nagar'}],is_city:true,
  requires_selection:true,terminal_group:{name:'Patna',codes:['PNBE','RJPB','PPTA']}};

test('typed city searches all its terminals by default',()=>{
  assert.deepEqual(resolveSearchEndpoint('Patna',city),{code:'Patna',display:'Patna'});
  assert.throws(()=>resolveSearchEndpoint('Patna',city,false),/Choose a station/);
});

test('selected station stays explicit even with nearby enabled',()=>{
  const station={...city,is_city:false,requires_selection:false};
  assert.deepEqual(resolveSearchEndpoint('Patna Jn (PNBE)',station,true),{code:'PNBE',display:'Patna Jn (PNBE)'});
  assert.deepEqual(resolveSearchEndpoint('PNBE',station,false),{code:'PNBE',display:'Patna Jn (PNBE)'});
  assert.throws(()=>resolveSearchEndpoint('Unknown',{stations:[]},true),/Choose a station/);
});

test('search includes nearby terminals by default and retains actual station metadata',async()=>{
  const previous=api.defaults.adapter;
  const previousStorage=globalThis.localStorage;
  globalThis.localStorage={getItem:()=>null};
  const calls=[];
  api.defaults.adapter=async config=>{
    calls.push(config.params);
    return {status:200,statusText:'OK',headers:{},config,data:{journeys:[{id:12,origin_code:'RJPB',destination_code:'KOAA',boarding_date:'2026-10-23'}]}};
  };
  try {
    const criteria={origin:'Patna',destination:'Kolkata',date:'2026-10-23',quota:'GN'};
    const rows=await getJourneys(criteria);
    assert.equal(calls[0].include_nearby,true);
    assert.equal(rows[0].origin_code,'RJPB');
    assert.equal(rows[0].destination_code,'KOAA');
    await getJourneys({...criteria,origin:'PNBE',destination:'HWH',includeNearby:false});
    assert.equal(calls[1].include_nearby,false);
  } finally {api.defaults.adapter=previous;globalThis.localStorage=previousStorage;}
});
