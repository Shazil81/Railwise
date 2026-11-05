import type { Journey } from './api';

export interface ResultFilters {
  departure: string; travelClass: string; maxFare: string; maxDuration: string; sort: string;
}
export const defaultFilters: ResultFilters = {departure:'any',travelClass:'any',maxFare:'',maxDuration:'',sort:'departure-asc'};

function clockMinutes(value:string):number|null {
  const match=value.replace('.',':').match(/^(\d{2}):(\d{2})$/);
  if(!match)return null;
  const hours=Number(match[1]),minutes=Number(match[2]);
  return hours<24&&minutes<60?hours*60+minutes:null;
}

export function journeyMetrics(journey:Journey,origin:string,destination:string) {
  const from=journey.stops.find(stop=>stop.code===(journey.origin_code||origin));
  const to=journey.stops.find(stop=>stop.code===(journey.destination_code||destination));
  const departure=from?clockMinutes(from.departure||from.arrival):null;
  const arrival=to?clockMinutes(to.arrival||to.departure):null;
  const elapsed=from&&to&&departure!==null&&arrival!==null?(to.day-from.day)*1440+arrival-departure:null;
  return {departure,duration:elapsed!==null&&elapsed>=0?elapsed:null};
}

export function durationLabel(minutes:number|null) {
  return minutes===null?'Duration unavailable':`${Math.floor(minutes/60)}h ${minutes%60}m`;
}

export function filterJourneys(journeys:Journey[],filters:ResultFilters,origin:string,destination:string):Journey[] {
  const upper=(value:string)=>value.trim()!==''&&Number.isFinite(Number(value))&&Number(value)>=0?Number(value):Infinity;
  const maxFare=upper(filters.maxFare),maxMinutes=upper(filters.maxDuration)*60;
  const windows:Record<string,[number,number]>={night:[0,360],morning:[360,720],afternoon:[720,1080],evening:[1080,1440]};
  const rows=journeys.flatMap(journey=>{
    const metrics=journeyMetrics(journey,origin,destination);
    const window=windows[filters.departure];
    if(window&&(metrics.departure===null||metrics.departure<window[0]||metrics.departure>=window[1]))return [];
    if(maxMinutes!==Infinity&&(metrics.duration===null||metrics.duration>maxMinutes))return [];
    const classes=journey.classes.filter(quote=>(filters.travelClass==='any'||quote.travel_class===filters.travelClass)&&Number(quote.total)<=maxFare);
    if(!classes.length)return [];
    return [{journey:{...journey,classes},...metrics,fare:Math.min(...classes.map(quote=>Number(quote.total)))}];
  });
  const [field,direction]=filters.sort.split('-');
  rows.sort((a,b)=>{
    const left=field==='fare'?a.fare:field==='duration'?a.duration:a.departure;
    const right=field==='fare'?b.fare:field==='duration'?b.duration:b.departure;
    if(left===null&&right!==null)return 1;
    if(right===null&&left!==null)return -1;
    return ((left??0)-(right??0))*(direction==='desc'?-1:1)||a.journey.number.localeCompare(b.journey.number);
  });
  return rows.map(row=>row.journey);
}
