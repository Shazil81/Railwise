import {loadRazorpaySdk} from '../razorpaySdk';
import usePageVisibility from '../usePageVisibility';
import { useEffect, useState } from 'react';
import { ArrowRight, ArrowLeft, Clock3, ShieldCheck, CheckCircle2, UserRound, Mail, Phone, LockKeyhole, Pencil } from 'lucide-react';
import { acceptFareReview, createRazorpayOrder, errorMessage, getBooking, recoverPayment, openRazorpayCheckout, savePassengerDetails } from '../api';
import type { Booking, Passenger, FareQuote } from '../api';
import './BookingCheckout.css';
import PaymentStatus from './PaymentStatus';
import BookingConfirmation from './BookingConfirmation';
import CancellationDialog from './CancellationDialog';
import BookingPreferences from './BookingPreferences';
import type { Preferences } from './BookingPreferences';
import PassengerEditor from './PassengerEditor';
import { berthLabels } from '../berths';
interface Props { initialBooking: Booking; onUpdated: (booking: Booking) => void }
const money = (value: string | number) => Number(value).toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });
export default function BookingCheckout({ initialBooking, onUpdated }: Props) {
  const [booking, setBooking] = useState(initialBooking);
  const [passengers, setPassengers] = useState<Passenger[]>(initialBooking.passengers);
  const [editor,setEditor]=useState<number|null>(null);
  const [email, setEmail] = useState(initialBooking.contact_email);
  const [phone, setPhone] = useState(initialBooking.contact_phone);
  const [stage, setStage] = useState<'details' | 'review'>(() => initialBooking.passengers.every(p => p.name && p.age && p.gender) && initialBooking.contact_email ? 'review' : 'details');
  const [accepted, setAccepted] = useState(false);
  const [preferences,setPreferences]=useState<Preferences>({confirmed_berths_only:Boolean(initialBooking.confirmed_berths_only),consider_auto_upgrade:Boolean(initialBooking.consider_auto_upgrade),preferred_coach:initialBooking.preferred_coach||'',gstin:initialBooking.gstin||''});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [cancelling,setCancelling]=useState(false);
  const [now, setNow] = useState(() => Date.now());
  const pageVisible=usePageVisibility();
  useEffect(() => {
    if(!pageVisible)return;
    const timer = booking.status==='PENDING' ? setInterval(() => setNow(Date.now()), 1000) : undefined;
    const refresh = setInterval(async () => {
      try { const current = await getBooking(initialBooking.booking_id); setBooking(current); } catch { /* Actions report service errors without discarding the form. */ }
    }, 15000);
    return () => { clearInterval(timer); clearInterval(refresh); };
  }, [initialBooking.booking_id,pageVisible,booking.status]);
  const remaining = booking.expires_at ? Math.max(0, Math.ceil((Date.parse(booking.expires_at) - now) / 1000)) : 0;
  const isPending = booking.status === 'PENDING';
  const paymentPending = (booking.payment_attempts || []).some(a => ['CREATED', 'AUTHORIZED', 'CAPTURED', 'REFUNDED', 'REVIEW'].includes(a.state));
  function update(next: Booking) { setBooking(next); onUpdated(next); }
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const saved = await savePassengerDetails(booking.booking_id, passengers, email, phone,preferences);
      update(saved); setPassengers(saved.passengers); setStage('review'); setAccepted(false);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  async function pay() {
    if (!accepted || busy || !remaining) return;
    setBusy(true); setError('');
    try {
      await loadRazorpaySdk();
      if (booking.razorpay_order_id) {
        const recovered = await recoverPayment(booking.booking_id);
        update(recovered);
        if (recovered.status !== 'PENDING' || recovered.payment_attempts.some(a => ['CREATED', 'AUTHORIZED', 'CAPTURED', 'REFUNDED', 'REVIEW'].includes(a.state))) { setBusy(false); return; }
      }
      const reviewed = await acceptFareReview(booking.booking_id);
      update(reviewed);
      const order = await createRazorpayOrder(booking.booking_id);
      const refreshed = await getBooking(booking.booking_id);
      update(refreshed);
      openRazorpayCheckout(order,
        confirmed => { update(confirmed); setBusy(false); },
        message => { setError(`${message} If payment was completed, check its status before retrying.`); setBusy(false); void getBooking(booking.booking_id).then(update).catch(() => {}); },
        () => { setBusy(false); setError('Checkout closed. If you completed payment, check its status before retrying.'); });
    } catch (e) { setError(errorMessage(e)); setBusy(false); }
  }
  if (booking.status === 'WL') return <section className="booking-checkout" aria-label="Waitlisted booking"><span className="eyebrow">BOOKING #{booking.booking_id}</span><h2>You’re on the waitlist</h2><p>{booking.train} · {booking.origin} → {booking.destination}</p><p>Position {booking.position}. Payment opens after a seat is allotted. Check My bookings for updates.</p><p>Requested berth: {berthLabels[booking.passengers[0]?.berth_preference||'ANY']}</p>{error&&<p className="error-box">{error}</p>}<button className="danger-outline" disabled={busy} onClick={()=>setCancelling(true)}>Cancel waitlist</button>{cancelling&&<CancellationDialog booking={booking} onUpdated={update} onClose={()=>setCancelling(false)}/>}</section>;
  if (booking.status === 'CONFIRMED' && booking.ticket_available) return <BookingConfirmation booking={booking} onUpdated={update}/>;
  return <section className="booking-checkout" aria-label="Passenger details and fare review">
    <div className="checkout-heading"><div><span className="eyebrow">BOOKING #{booking.booking_id}</span><h2>Review and pay</h2><p>{booking.train} · {booking.origin} → {booking.destination}<br/>{new Date(`${booking.date}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</p></div>{isPending && <span className={`hold-clock ${remaining < 60 ? 'urgent' : ''}`}><Clock3 size={16}/>{Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, '0')} left</span>}</div>
    <ol className="checkout-steps" aria-label="Booking progress"><li className={stage === 'details' && isPending ? 'current' : 'complete'}><span>1</span> Passenger details</li><li className={stage === 'review' && isPending ? 'current' : ''}><span>2</span> Review fare</li><li className={booking.status === 'CONFIRMED' ? 'complete' : ''}><span>3</span> Razorpay payment</li></ol>
    <PaymentStatus booking={booking} onUpdated={update}/>
    {paymentPending && isPending && <p className="payment-hold-notice">A payment is being verified or needs review. Check payment status before starting another payment.</p>}
    {error && <div role="alert" className="error-box">{error}</div>}
    {!isPending || !remaining ? <div className="checkout-result"><CheckCircle2 size={32}/><h3>{booking.status === 'CONFIRMED' ? 'Confirmation needs verification.' : booking.status === 'CANCELLED' ? 'Your seats have been released.' : 'Your seat hold has expired.'}</h3><p>{booking.passengers.length} passenger{booking.passengers.length === 1 ? '' : 's'}</p><p>{booking.status === 'CONFIRMED' ? 'Your passenger and seat details are saved in booking history.' : 'Choose a train and class to start a new booking.'}</p></div> : stage === 'details' ? <form onSubmit={save}>
      <div className="checkout-grid"><div className="traveller-panel"><div className="panel-title"><UserRound size={18}/><div><h3>Who’s travelling?</h3><p>One reserved seat per passenger · Ages 1–120</p></div></div>
      <div className="passenger-summary-list">{passengers.map((p,index)=><article className="passenger-summary-card" key={p.booking_id}><span className="traveller-avatar">{p.name.charAt(0).toUpperCase()||String(index+1)}</span><div><strong>{p.name||`Passenger ${index+1}`}</strong><p>{p.age?`${p.age} years · ${p.gender} · ${p.country||'India'}`:'Passenger details pending'}</p><span className="requested-berth">{berthLabels[p.berth_preference||'ANY']}</span></div><div className="traveller-actions"><button type="button" aria-label={`Edit passenger ${index+1}`} disabled={busy} onClick={()=>setEditor(index)}><Pencil size={16}/></button></div></article>)}</div>
      <div className="contact-form"><h3>Booking contact</h3><p>Use fictional passenger details. Booking updates go only to your verified account email. No SMS is sent.</p><label><span><Mail size={13}/> Email address</span><input type="email" autoComplete="email" aria-label="Contact email" value={email} onChange={e => setEmail(e.target.value)} required maxLength={254} placeholder="traveller@example.com" disabled={busy}/></label><label><span><Phone size={13}/> Mobile number</span><input type="tel" inputMode="numeric" autoComplete="tel-national" aria-label="Contact mobile" pattern="[6-9][0-9]{9}" minLength={10} maxLength={10} value={phone} onChange={e => setPhone(e.target.value)} required placeholder="10-digit Indian mobile" disabled={busy}/></label></div></div>
      <aside className="fare-summary"><span className="eyebrow">Journey summary</span><h3>{booking.origin}<ArrowRight size={17}/>{booking.destination}</h3><p>{new Date(`${booking.date}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}</p><div className="allocation-pending"><Clock3 size={20}/><span>Coach and berth details will appear after booking confirmation.</span></div><dl><div><dt>Passengers</dt><dd>{passengers.length}</dd></div><div><dt>Held fare per passenger</dt><dd>{money(passengers[0]?.fare || 0)}</dd></div><div className="fare-total"><dt>Total</dt><dd>{money(booking.fare_breakdown.total)}</dd></div></dl><FareRuleBreakdown details={booking.fare_details}/><p className="fare-disclaimer">Illustrative project fare, not an Indian Railways tariff. Availability is temporarily held while you complete payment.</p><div className="privacy-note"><ShieldCheck size={16}/> Details are saved to your account. No ID document upload is needed.</div></aside></div>
      <BookingPreferences value={preferences} onChange={setPreferences} disabled={busy||Boolean(booking.razorpay_order_id)}/>
      <div className="checkout-actions"><button type="button" className="danger-outline" onClick={()=>setCancelling(true)} disabled={busy}>Cancel booking</button><button className="primary" disabled={busy}>{busy ? 'Saving passengers…' : 'Continue to fare review'}<ArrowRight size={16}/></button></div>
    </form> : <div>
      <p className="preference-summary">Confirmed berths only: {booking.confirmed_berths_only?'Yes':'No'} · Auto-upgradation: {booking.consider_auto_upgrade?'Opted in':'Not requested'}{booking.allocated_class&&booking.allocated_class!==booking.travel_class?` · Upgraded ${booking.travel_class} → ${booking.allocated_class} at original fare`: ''}</p><p className="preference-summary">{booking.preferred_coach?`Preferred coach: ${booking.preferred_coach} · Subject to availability`: 'No coach preference'}{booking.gstin?` · GSTIN: ${booking.gstin}`:''}</p><div className="review-heading"><h3>Review your journey.</h3><p>Check your passengers, berth preferences and fare before payment.</p></div><div className="checkout-grid"><div><div className="allocation-pending"><Clock3 size={22}/><div><strong>Coach & berth details after confirmation</strong><p>Your preference is a request, not an allotted berth. Availability is held temporarily while you pay.</p></div></div><div className="review-travellers">{booking.passengers.map((p, index) => <div key={p.booking_id}><span className="passenger-number">{index + 1}</span><div><strong>{p.name}</strong><p>{p.age} years · {p.gender}{p.country?` · ${p.country}`:''}</p></div><span className="review-seat"><small>Berth preference</small>{berthLabels[p.berth_preference||'ANY']}<small>Subject to availability</small></span><strong>{money(p.fare)}</strong></div>)}</div><div className="review-contact"><Mail size={16}/><div><strong>Booking contact</strong><p>{booking.contact_email}<br/>{booking.contact_phone}</p></div></div>{booking.razorpay_order_id ? <p className="locked-note"><LockKeyhole size={14}/> Passenger details are locked because a payment order has been created.</p> : <button className="text-button edit-passengers" onClick={() => { setStage('details'); setAccepted(false); }} disabled={busy}><ArrowLeft size={14}/> Edit passenger details</button>}</div><aside className="fare-summary"><span className="eyebrow">Fare breakdown</span><h3>{booking.passengers.length} passenger{booking.passengers.length===1?'':'s'}, one payment.</h3><dl>{booking.passengers.map(p => <div key={p.booking_id}><dt>{p.name}</dt><dd>{money(p.fare)}</dd></div>)}<div><dt>Booking fee</dt><dd>{money(booking.fare_breakdown.booking_fee)}</dd></div><div className="fare-total"><dt>Total payable</dt><dd>{money(booking.fare_breakdown.total)}</dd></div></dl><FareRuleBreakdown details={booking.fare_details}/><p className="fare-disclaimer">{booking.fare_breakdown.label}. Your held fare is fixed until the hold expires. {import.meta.env.DEV&&booking.payment_mode==='test'?'Razorpay Test Mode does not debit real money.':''}</p></aside></div>
      <label className="review-consent"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} disabled={busy}/>I have checked all passenger details, berth preferences and the total fare.</label><div className="checkout-actions"><button className="danger-outline" disabled={busy} onClick={()=>setCancelling(true)}>Cancel booking</button><button className="primary" disabled={!accepted || busy || !remaining || paymentPending} onClick={pay}>{busy ? 'Preparing secure checkout…' : `Pay ${money(booking.fare_breakdown.total)} with Razorpay`}<ArrowRight size={16}/></button></div><p className="gateway-note"><ShieldCheck size={13}/> You’ll continue to Razorpay. Booking is confirmed only after server verification.</p>
    </div>}{cancelling&&<CancellationDialog booking={booking} onUpdated={update} onClose={()=>setCancelling(false)}/ >}{editor!==null&&<PassengerEditor key={editor} initial={passengers[editor]} travelClass={passengers[editor].allocated_class||booking.allocated_class||booking.travel_class} onClose={()=>setEditor(null)} onSave={passenger=>{setPassengers(rows=>rows.map((p,index)=>index===editor?{...p,...passenger}:p));setEditor(null);}}/>}
  </section>;
}

function FareRuleBreakdown({details}:{details:Partial<FareQuote>}) {
 if(!details?.total)return null;
 return <details className="stored-fare"><summary>Per passenger breakdown · {details.travel_class} · {details.quota==='TQ'?'Tatkal':'General'}</summary><p>{details.distance_km} km · {details.class_name}</p><dl><div><dt>Distance fare</dt><dd>{money(details.base_fare||0)}</dd></div><div><dt>Reservation</dt><dd>{money(details.reservation_fee||0)}</dd></div><div><dt>Demand surcharge</dt><dd>{money(details.demand_surcharge||0)}</dd></div><div><dt>Tatkal surcharge</dt><dd>{money(details.tatkal_surcharge||0)}</dd></div></dl></details>;
}
