import { useEffect, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { Journey } from './api';
import { inventorySegments, mergeInventory } from './inventory';
import { API_BASE_URL } from './apiBase';

export function useSeatInventory(journeys:Journey[],enabled:boolean,setJourneys:Dispatch<SetStateAction<Journey[]>>) {
  const [status,setStatus]=useState('Connecting to seat updates…');
  const segments=JSON.stringify(inventorySegments(journeys));
  useEffect(()=>{
    if(!enabled||segments==='[]')return;
    let active=true;
    let stream:EventSource;
    let timer:ReturnType<typeof setTimeout>|undefined;
    let failures=0;
    const connect=()=>{
      if(!active)return;
      stream=new EventSource(API_BASE_URL+'/inventory/stream/?segments='+encodeURIComponent(segments));
      stream.addEventListener('inventory',event=>{
      if(!active)return;
      try {
        const update=JSON.parse((event as MessageEvent).data);
        if(!Array.isArray(update.journeys))throw Error('Invalid inventory update');
        setJourneys(previous=>mergeInventory(previous,update));
        failures=0;
        setStatus('Live seat updates');
      } catch {setStatus('Seat updates unavailable · refresh to retry');}
      });
      stream.onerror=()=>{
        stream.close();
        if(!active)return;
        setStatus('Reconnecting to seat updates…');
        timer=setTimeout(connect,Math.min(15000,2000*2**failures++));
      };
    };
    connect();
    return()=>{active=false;clearTimeout(timer);stream?.close();};
  },[segments,enabled,setJourneys]);
  return status;
}
