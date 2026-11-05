import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, TrainFront, Plus, Trash2, Pencil, Users, ShieldCheck, Mail } from 'lucide-react';
import { bookAutomatically, errorMessage, getBooking, getJourney, getJourneyQuote } from '../api';
import type { Booking, Journey, FareQuote, NewPassenger } from '../api';
import BookingCheckout from '../components/BookingCheckout';
import BookingPreferences from '../components/BookingPreferences';
import { berthLabels } from '../berths';
import PassengerEditor from '../components/PassengerEditor';
import type { Preferences } from '../components/BookingPreferences';
import { boardingDate } from '../bookingDate';
import './BookingPage.css';

const money=(value:string|number)=>Number(value).toLocaleString('en-IN',{style:'currency',currency:'INR'});

export default function BookingPage({authenticated,onSignIn}:{authenticated:boolean;onSignIn:()=>void}) {
  const {journeyId,bookingId}=useParams();
  const [params]=useSearchParams();
  const navigate=useNavigate();
  const from=Number(params.get('from')),to=Number(params.get('to')),travelClass=params.get('class')||'SL',quota=params.get('quota')||'GN';
  const [journey,setJourney]=useState<Journey|null>(null),[quote,setQuote]=useState<FareQuote|null>(null);
  const [booking,setBooking]=useState<Booking|null>(null);
  const [passengers,setPassengers]=useState<NewPassenger[]>([]);
  const [editor,setEditor]=useState<number|null>(null);
  const [email,setEmail]=useState(''),[phone,setPhone]=useState('');
  const [preferences,setPreferences]=useState<Preferences>({confirmed_berths_only:false,consider_auto_upgrade:false,preferred_coach:'',gstin:''});
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState('');
  useEffect(()=>{
    let active=true;
    const timer=setTimeout(async()=>{
      setLoading(true);setError('');setBooking(null);setJourney(null);setQuote(null);
      try {
        if(bookingId) {
          if(!authenticated)return;
          const b=await getBooking(Number(bookingId));if(active)setBooking(b);
        } else {
          const [j,q]=await Promise.all([getJourney(Number(journeyId)),getJourneyQuote(Number(journeyId),from,to,travelClass,quota)]);
          if(active){setJourney(j);setQuote(q);}
        }
      } catch(e){if(active)setError(errorMessage(e));}
      finally{if(active)setLoading(false);}
    },0);
    return()=>{active=false;clearTimeout(timer);};
  },[journeyId,bookingId,from,to,travelClass,quota,authenticated]);
  useEffect(()=>{window.scrollTo(0,0);},[journeyId,bookingId]);
  async function submit(event:React.FormEvent) {
    event.preventDefault();if(busy)return;if(!passengers.length){setError('Add at least one passenger before continuing.');return;}if(!authenticated){onSignIn();return;}
    setBusy(true);setError('');
    try {
      const b=await bookAutomatically({journey_id:Number(journeyId),from_seq:from,to_seq:to,travel_class:travelClass,quota,
        passengers,contact_email:email,contact_phone:phone,...preferences});
      navigate(`/booking/${b.booking_id}`,{replace:true});
    }catch(e){setError(errorMessage(e));}finally{setBusy(false);}
  }
  const origin=journey?.stops.find(s=>s.sequence===from),destination=journey?.stops.find(s=>s.sequence===to);
  return <div className="rail-app booking-route-page"><header className="topbar"><Link className="brand" to="/"><span className="brand-icon"><TrainFront size={24}/></span>Railwise</Link><Link className="secondary" to="/"><ArrowLeft size={15}/> Back to train results</Link></header>
    <main id="booking-main" tabIndex={-1} className="main-content local-main">
      {error&&<div className="error-box" role="alert">{error}</div>}
      {loading?<p className="empty-state">Loading your journey…</p>:bookingId?(!authenticated?<div className="empty-state"><h2>Sign in to continue your booking</h2><button className="primary" onClick={onSignIn}>Sign in</button></div>:booking&&<BookingCheckout key={booking.booking_id} initialBooking={booking} onUpdated={setBooking}/>):!authenticated?<div className="empty-state"><ShieldCheck size={32}/><h2>Sign in to book your journey</h2><p>You can search and compare trains freely. Sign in to add passengers and reserve your booking.</p><button className="primary" onClick={onSignIn}>Sign in to continue</button></div>:journey&&quote&&<section className="booking-checkout" aria-label="Passenger details">
        <ol className="booking-stage-strip" aria-label="Booking progress"><li className="active"><b>1</b>Passenger details</li><li><b>2</b>Review journey</li><li><b>3</b>Secure payment</li></ol><span className="eyebrow">MAKE IT YOUR JOURNEY</span><h1>A comfortable journey starts here.</h1>
        <p>{journey.train} · #{journey.number} · {origin?.name} ({origin?.code}) → {destination?.name} ({destination?.code})</p>
        <p>{boardingDate(journey.date,origin?.day||1)} · {quote.class_name} · {quota==='TQ'?'Tatkal':'General'} quota</p>
        <p className="allocation-note"><ShieldCheck size={19}/> Choose a berth preference for each passenger. Preferences are subject to availability. Coach and berth details appear after booking confirmation.</p>
        {!authenticated&&<p className="allocation-note">Sign in before continuing. <button className="text-button" onClick={onSignIn}>Sign in</button></p>}
        {quote.booking_open===false&&<p className="error-box">{quote.booking_error}</p>}
        <form onSubmit={submit}><div className="checkout-grid"><div className="traveller-panel">
          <section className="passenger-list-panel"><div className="passenger-panel-heading"><span className="passenger-section-icon"><Users size={22}/></span><div><h2>Passenger Details</h2><p>Add up to 6 travellers. Your berth, your preference.</p></div><span className="passenger-limit">{passengers.length}/6</span></div>
          {!passengers.length&&<div className="passenger-empty"><Users size={32}/><h3>Who’s joining the journey?</h3><p>Add a passenger to get started.</p></div>}
          <div className="passenger-summary-list">{passengers.map((p,index)=><article className="passenger-summary-card" key={index}><span className="traveller-avatar">{p.name.charAt(0).toUpperCase()}</span><div><strong>{p.name}</strong><p>{p.age} years · {p.gender} · {p.country||'India'}</p><span className="requested-berth">{berthLabels[p.berth_preference||'ANY']}</span></div><div className="traveller-actions"><button type="button" aria-label={`Edit passenger ${index+1}`} disabled={busy} onClick={()=>setEditor(index)}><Pencil size={16}/></button><button type="button" aria-label={`Remove passenger ${index+1}`} disabled={busy} onClick={()=>setPassengers(rows=>rows.filter((_,i)=>i!==index))}><Trash2 size={16}/></button></div></article>)}</div>
          <button type="button" className="add-passenger-button" disabled={busy||passengers.length>=6} onClick={()=>setEditor(-1)}><Plus size={20}/> Add Passenger</button></section>
          <div className="contact-form"><h3><Mail size={19}/> Contact Details</h3><p>Use fictional passenger details for this demo. Emails go only to your verified account email.</p><label>Email address<input aria-label="Contact email" type="email" required maxLength={254} disabled={busy} value={email} onChange={e=>setEmail(e.target.value)}/></label><label>Mobile number<input aria-label="Contact mobile" type="tel" required pattern="[6-9][0-9]{9}" maxLength={10} disabled={busy} value={phone} onChange={e=>setPhone(e.target.value)}/></label></div>
        </div><aside className="fare-summary"><span className="eyebrow">YOUR JOURNEY</span><h3>{origin?.code} → {destination?.code}</h3><p>Departure {origin?.departure} · Arrival {destination?.arrival} · All times IST</p><dl><div><dt>Passengers</dt><dd>{passengers.length}</dd></div><div><dt>Current fare per passenger</dt><dd>{money(quote.total)}</dd></div><div className="fare-total"><dt>Estimated total</dt><dd>{money(Number(quote.total)*passengers.length)}</dd></div></dl><p>Fare and availability are checked again when you continue. A successful allocation holds all seats for 10 minutes.</p><p>Berth preferences are requests and cannot be guaranteed. No seats are held while filling this form. If a single passenger has no seat available and confirmed-berths-only is off, they can join the waitlist. Multi-passenger bookings require seats for everyone.</p></aside></div>
        <BookingPreferences value={preferences} onChange={setPreferences} disabled={busy}/><div className="checkout-actions"><Link className="text-button" to="/">Back to results</Link><button className="primary" disabled={busy||!passengers.length||quote.booking_open===false}>{busy?'Allotting berths…':'Continue to fare review'}<ArrowRight size={16}/></button></div></form>{editor!==null&&<PassengerEditor key={editor} initial={editor>=0?passengers[editor]:undefined} travelClass={travelClass} onClose={()=>setEditor(null)} onSave={passenger=>{setPassengers(rows=>editor<0?[...rows,passenger]:rows.map((p,index)=>index===editor?passenger:p));setEditor(null);setError('');}}/>}
      </section>}
    </main></div>;
}
