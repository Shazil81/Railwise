import test from 'node:test';
import assert from 'node:assert/strict';
import { filterJourneys, journeyMetrics, durationLabel, defaultFilters } from '../src/results.ts';
function train(number,departure,arrival,endDay,classes,startDay=1) {
  return {id:Number(number),number,train:number,origin_code:'RJPB',destination_code:'KOAA',date:'2026-10-23',
    stops:[{code:'RJPB',sequence:2,departure,arrival:'',day:startDay},{code:'KOAA',sequence:5,arrival,departure:'',day:endDay}],
    classes:classes.map(([travel_class,total])=>({travel_class,total:String(total)}))};
}
const rows=[train('1','22:30','07:30',2,[['SL',350],['3A',850]]),train('2','06:00','12:00',1,[['CC',500]]),train('3','14:00','23:30',1,[['SL',300],['3A',950]])];
const filtered=changes=>filterJourneys(rows,{...defaultFilters,...changes},'PNBE','HWH');

test('duration uses actual nearby terminals and route day offsets, including multi-day trips',()=>{
  assert.equal(journeyMetrics(rows[0],'PNBE','HWH').duration,540);
  assert.equal(journeyMetrics(train('4','23:00','06:00',4,[['SL',300]],2),'PNBE','HWH').duration,1860);
  assert.equal(durationLabel(540),'9h 0m');
});
test('departure window boundaries are inclusive at start and exclusive at end',()=>{
  assert.deepEqual(filtered({departure:'morning'}).map(row=>row.number),['2']);
  assert.deepEqual(filtered({departure:'evening'}).map(row=>row.number),['1']);
  assert.deepEqual(filtered({departure:'night'}),[]);
});
test('class and fare filters apply to the same displayed class',()=>{
  assert.deepEqual(filtered({travelClass:'3A',maxFare:'900'}).map(row=>row.number),['1']);
  assert.deepEqual(filtered({travelClass:'3A',maxFare:'400'}),[]);
  assert.deepEqual(filtered({travelClass:'SL',sort:'fare-asc'}).map(row=>row.number),['3','1']);
  assert.deepEqual(filtered({travelClass:'3A'})[0].classes.map(quote=>quote.travel_class),['3A']);
});
test('sorting and duration filtering respect overnight duration and selected-class prices',()=>{
  assert.deepEqual(filtered({sort:'duration-asc'}).map(row=>row.number),['2','1','3']);
  assert.deepEqual(filtered({sort:'duration-desc'}).map(row=>row.number),['3','1','2']);
  assert.deepEqual(filtered({sort:'fare-desc'}).map(row=>row.number),['2','1','3']);
  assert.deepEqual(filtered({sort:'departure-desc'}).map(row=>row.number),['1','3','2']);
  assert.deepEqual(filtered({maxDuration:'6'}).map(row=>row.number),['2']);
  assert.deepEqual(filtered({maxFare:'0'}),[]);
  assert.equal(rows[0].classes.length,2);
  assert.deepEqual(rows.map(row=>row.number),['1','2','3']);
});
test('unknown timetable times sort last and cannot satisfy a time/duration filter',()=>{
  const unknown=train('5','','',1,[['SL',100]]);
  assert.equal(journeyMetrics(unknown,'PNBE','HWH').duration,null);
  const list=[unknown,...rows];
  assert.equal(filterJourneys(list,{...defaultFilters,sort:'duration-desc'},'PNBE','HWH').at(-1).number,'5');
  assert.equal(filterJourneys(list,{...defaultFilters,maxDuration:'20'},'PNBE','HWH').some(row=>row.number==='5'),false);
});
