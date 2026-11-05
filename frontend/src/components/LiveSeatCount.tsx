import { useEffect, useRef } from 'react';
export default function LiveSeatCount({count}:{count:number}) {
  const node=useRef<HTMLSpanElement>(null),previous=useRef(count);
  useEffect(()=>{
    if(previous.current!==count&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      node.current?.animate([{backgroundColor:'#a7f3d0',color:'#065f46'},{backgroundColor:'transparent',color:'inherit'}],{duration:900,easing:'ease-out'});
    }
    previous.current=count;
  },[count]);
  return <span className="live-seat-count" ref={node} aria-live="polite" aria-atomic="true">{count} {count?'seats available':'seats · Join waitlist'}</span>;
}
