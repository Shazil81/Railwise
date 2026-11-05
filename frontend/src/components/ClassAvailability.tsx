import { useRef, useState } from 'react';
import { RefreshCw,Info,ArrowLeft,ArrowRight } from 'lucide-react';
import type { FareQuote } from '../api';
import LiveSeatCount from './LiveSeatCount';
import './ClassAvailability.css';

const names:Record<string,string>={'1A':'AC First Class (1A)','2A':'AC 2 Tier (2A)','3A':'AC 3 Tier (3A)',SL:'Sleeper (SL)',CC:'AC Chair Car (CC)',EC:'Executive Chair (EC)'};
const order=['1A','2A','3A','SL','CC','EC'];
export default function ClassAvailability({quotes,selected,onSelect,onRefresh}:{quotes:FareQuote[];selected:string|null;onSelect:(code:string)=>void;onRefresh:(code:string)=>Promise<void>}) {
  const [busy,setBusy]=useState<string|null>(null),[error,setError]=useState('');
  const scroll=useRef<HTMLDivElement>(null);
  function browse(direction:number){scroll.current?.scrollBy({left:direction*280,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});}
  async function refresh(code:string) {setBusy(code);setError('');try{await onRefresh(code);}catch{setError('Could not refresh this class. Please retry.');}finally{setBusy(null);}}
  return <section className="available-classes" aria-label="Available classes"><div className="availability-heading"><h3>Choose your class</h3><div className="class-scroll-actions"><button type="button" aria-label="Previous classes" onClick={()=>browse(-1)}><ArrowLeft size={18}/></button><button type="button" aria-label="Next classes" onClick={()=>browse(1)}><ArrowRight size={18}/></button></div></div>
    <div ref={scroll} className="availability-scroll" tabIndex={0} aria-label="Scroll available classes horizontally">
      {[...quotes].sort((a,b)=>order.indexOf(a.travel_class)-order.indexOf(b.travel_class)).map(quote=><div key={quote.travel_class} className={`availability-tile ${selected===quote.travel_class?'is-selected':''}`}>
        <div className="availability-title"><h4>{names[quote.travel_class]||quote.class_name}</h4><button type="button" className="class-refresh" disabled={busy!==null} onClick={()=>void refresh(quote.travel_class)} aria-label={`Refresh ${names[quote.travel_class]||quote.class_name}`}><RefreshCw size={21} className={busy===quote.travel_class?'is-refreshing':''}/></button></div>
        <div className={`availability-status ${quote.available_seats?'has-seats':'is-waitlisted'}`}>{quote.booking_error||<LiveSeatCount count={quote.available_seats}/>}</div>
        <div className="availability-bottom"><div><strong>{Number(quote.total).toLocaleString('en-IN',{style:'currency',currency:'INR',minimumFractionDigits:2,maximumFractionDigits:2})}</strong><span className="fare-info" role="img" aria-label="Project fare per passenger, not an official railway tariff" title="Project fare per passenger, not an official railway tariff"><Info size={17}/></span><small>Per passenger</small></div><button type="button" className="class-book" disabled={quote.booking_open===false} aria-label={`Book ${names[quote.travel_class]||quote.class_name}`} aria-haspopup="dialog" aria-expanded={selected===quote.travel_class} onClick={()=>onSelect(quote.travel_class)}>{selected===quote.travel_class?'SELECTED':'BOOK'}</button></div>
      </div>)}
    </div>{error&&<p role="alert" className="class-refresh-error">{error}</p>}
  </section>;
}
