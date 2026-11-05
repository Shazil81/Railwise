import type { Booking } from './api';
export const classNames:Record<string,string>={'CC':'AC Chair Car','EC':'Executive Chair Car','SL':'Sleeper','1A':'AC First Class','2A':'AC 2 Tier','3A':'AC 3 Tier','3E':'AC 3 Economy'};
export const formatMoney=(value:string|number)=>Number(value).toLocaleString('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:2,maximumFractionDigits:2});
export const displayName=(value:string)=>value.trim().toLocaleLowerCase('en-IN').replace(/(^|[\s'-])\p{L}/gu,letter=>letter.toLocaleUpperCase('en-IN'));
export const maskEmail=(email:string)=>{const [name,domain]=email.split('@');return domain?`${name.charAt(0)}***@${domain}`:'';};
export const dateTime=(value?:string|null)=>value?new Date(value).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' IST':'Not recorded';
export const clockTime=(value?:string|null)=>value?new Date(value).toLocaleTimeString('en-IN',{timeZone:'Asia/Kolkata',hour:'2-digit',minute:'2-digit',hour12:false}):'—';
export const journeyDate=(value:string)=>new Date(value.slice(0,10)+'T12:00:00+05:30').toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'short',year:'numeric'});
export function durationText(minutes?:number|null){return minutes==null?'Duration unavailable':`${Math.floor(minutes/60)}h ${minutes%60}m`;}
export function departureCountdown(value?:string|null,now=Date.now()){
 if(!value)return 'Departure time unavailable';const minutes=Math.ceil((Date.parse(value)-now)/60000);
 if(minutes<=0)return 'Departed';if(minutes>=1440)return `Departs in ${Math.floor(minutes/1440)} day${minutes>=2880?'s':''}`;
 if(minutes>=60)return `Departs in ${Math.floor(minutes/60)}h ${minutes%60}m`;return `Departs in ${minutes} min`;
}
export type BookingFilter='all'|'upcoming'|'past'|'cancelled';
export function matchesBookingFilter(b:Booking,filter:BookingFilter,now=Date.now()){
 if(filter==='all')return true;if(filter==='cancelled')return ['CANCELLED','EXPIRED'].includes(b.status);
 if(['CANCELLED','EXPIRED'].includes(b.status))return false;
 const departure=b.departure_at?Date.parse(b.departure_at):Date.parse(b.date+'T23:59:59+05:30');return filter==='upcoming'?departure>now:departure<=now;
}
function escapeCalendar(value:string){return value.replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');}
function foldCalendar(line:string){const parts:string[]=[];let current='',bytes=0;for(const char of line){const size=new TextEncoder().encode(char).length;if(bytes+size>73){parts.push(current);current=' ';bytes=1;}current+=char;bytes+=size;}return [...parts,current].join('\r\n');}
export function calendarEvent(b:Booking,now=new Date()){
 if(b.status!=='CONFIRMED'||!b.ticket_available||!b.departure_at||!b.arrival_at)return null;
 if(!Number.isFinite(Date.parse(b.departure_at))||!Number.isFinite(Date.parse(b.arrival_at))||Date.parse(b.arrival_at)<=Date.parse(b.departure_at))return null;
 const stamp=(value:string|Date)=>new Date(value).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
 return ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Railwise//Journey Calendar//EN','CALSCALE:GREGORIAN','BEGIN:VEVENT',`UID:${b.booking_reference}@railwise.local`,`DTSTAMP:${stamp(now)}`,`DTSTART:${stamp(b.departure_at)}`,`DTEND:${stamp(b.arrival_at)}`,`SUMMARY:${escapeCalendar(`${b.train} #${b.train_number}`)}`,`LOCATION:${escapeCalendar(`${b.origin} to ${b.destination}`)}`,'DESCRIPTION:Railwise portfolio demo booking. Not valid for travel.','END:VEVENT','END:VCALENDAR'].map(foldCalendar).join('\r\n')+'\r\n';
}
