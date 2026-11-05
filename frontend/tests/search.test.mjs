import test from 'node:test';
import assert from 'node:assert/strict';
import { stationCode, indiaToday, resolveStationChoice } from '../src/search.ts';

test('station selection uses its code and supports manually typed codes', () => {
  assert.equal(stationCode('New Delhi (NDLS)'), 'NDLS');
  assert.equal(stationCode(' ndls '), 'NDLS');
  assert.equal(stationCode('Hazrat Nizamuddin (NZM)'), 'NZM');
  assert.equal(stationCode('New Delhi'), '');
  assert.equal(stationCode('../NDLS'), '');
  assert.equal(stationCode(''), '');
});
test('city names resolve to verified stations instead of being uppercased into bogus codes', () => {
  const choices=[{code:'PNBE',name:'Patna Jn'},{code:'PTG',name:'Patna Ghat'},{code:'PNC',name:'Patna Saheb'}];
  assert.equal(resolveStationChoice('patna',choices)?.code,'PNBE');
  assert.equal(resolveStationChoice('PNBE',choices)?.code,'PNBE');
  assert.equal(resolveStationChoice('Patna Jn (PNBE)',choices)?.code,'PNBE');
  assert.equal(resolveStationChoice('kolkata',[{code:'KOAA',name:'Kolkata'}])?.code,'KOAA');
  assert.equal(resolveStationChoice('PATNA',[]),null);
  assert.equal(resolveStationChoice('Patna', [...choices,{code:'OTHER',name:'Patna Junction'}]),null);
  assert.equal(resolveStationChoice('Delhi',[{code:'NDLS',name:'New Delhi'},{code:'DLI',name:'Old Delhi'}]),null);
  assert.equal(resolveStationChoice('kolkata',[{code:'CP',name:'Kolkata'}],false),null);
  assert.equal(resolveStationChoice('koaa',[{code:'KOAA',name:'Kolkata Chitpur'}],false)?.code,'KOAA');
});
test('calendar minimum is an ISO date in India', () => {
  assert.match(indiaToday(), /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(indiaToday(), new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
});
