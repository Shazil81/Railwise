import type { Journey } from './api';

export interface InventoryUpdate {
  journeys:{id:number;from_seq:number;to_seq:number;classes:{travel_class:string;available_seats:number;capacity:number}[]}[];
}
export function inventorySegments(journeys:Journey[]) {
  return journeys.flatMap(row=>{
    const from=row.stops.find(stop=>stop.code===row.origin_code),to=row.stops.find(stop=>stop.code===row.destination_code);
    return from&&to?[[row.id,from.sequence,to.sequence]]:[];
  });
}
export function mergeInventory(journeys:Journey[],update:InventoryUpdate) {
  let changed=false;
  const rows=journeys.map(row=>{
    const from=row.stops.find(stop=>stop.code===row.origin_code),to=row.stops.find(stop=>stop.code===row.destination_code);
    const next=update.journeys.find(item=>item.id===row.id&&item.from_seq===from?.sequence&&item.to_seq===to?.sequence);
    if(!next||!Array.isArray(next.classes))return row;
    const classes=row.classes.map(quote=>{
      const value=next.classes.find(item=>item.travel_class===quote.travel_class);
      if(!value||!Number.isInteger(value.available_seats)||!Number.isInteger(value.capacity)||value.available_seats<0||value.available_seats>value.capacity)return quote;
      if(quote.available_seats===value.available_seats&&quote.capacity===value.capacity)return quote;
      changed=true;return {...quote,available_seats:value.available_seats,capacity:value.capacity};
    });
    return {...row,classes};
  });
  return changed?rows:journeys;
}
