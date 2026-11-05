import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Download, TrainFront, ArrowRight, Users, CreditCard, ShieldCheck, RefreshCw } from 'lucide-react';
import { getConfirmation, downloadTicket, errorMessage } from '../api';
import type { Booking, Confirmation } from '../api';
import PaymentStatus from './PaymentStatus';
import CancellationDialog from './CancellationDialog';
import { berthLabels } from '../berths';
import './BookingConfirmation.css';
import {displayName,clockTime,journeyDate,durationText,classNames,dateTime} from '../bookingDisplay';
const money=(value:string)=>Number(value).toLocaleString('en-IN',{style:'currency',currency:'INR'});
export default function BookingConfirmation({booking,onUpdated}: {booking:Booking;onUpdated:(next:Booking)=>void}) {
  const [ticket,setTicket]=useState<Confirmation|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [downloading,setDownloading]=useState(false);
  const [notice,setNotice]=useState('');
  const [cancelling,setCancelling]=useState(false);
  const load=useCallback(async()=>{
    setLoading(true);setError('');
    try{setTicket(await getConfirmation(booking.booking_id));}
    catch(e){setTicket(null);setError(errorMessage(e));}
    finally{setLoading(false);}
  },[booking.booking_id]);
  useEffect(()=>{const timer=setTimeout(load,0);return()=>clearTimeout(timer);},[load]);
  async function download(){
    setDownloading(true);setError('');setNotice('');
    try{await downloadTicket(booking.booking_id);setNotice('Your demo PDF ticket download has started.');}
    catch(e){setError(errorMessage(e));}
    finally{setDownloading(false);}
  }
  if(loading)return <section className="confirmation-page"><p className="empty-state">Preparing your booking confirmation…</p></section>;
  return <section className="confirmation-page" aria-label="Booking confirmation">
    {error&&<div className="error-box" role="alert">{error}</div>}
    {!ticket?<div className="empty-state"><h3>Confirmation is not available.</h3><p>The booking may have been cancelled, refunded or still needs payment verification.</p><button className="secondary" onClick={load}><RefreshCw size={14}/> Refresh confirmation</button></div>:<>
    <div className="confirmation-banner"><span className="confirmation-check"><CheckCircle2 size={30}/></span><div><span className="eyebrow">PAYMENT VERIFIED · SEATS CONFIRMED</span><h2>You’re all set for your journey.</h2><p>{ticket.passengers.length} passenger{ticket.passengers.length>1?'s':''}, one booking. Your details are saved and ready to download.</p></div><button className="primary" disabled={downloading} onClick={download}><Download size={16}/>{downloading?'Preparing PDF…':'Download PDF ticket'}</button></div>
    <div className="confirmation-demo"><ShieldCheck size={16}/><span>Portfolio demo ticket · Not valid for travel · Not affiliated with IRCTC or Indian Railways.</span></div>
    <div className="confirmation-ticket"><div className="confirmation-ticket-top"><div className="confirmation-brand"><TrainFront size={20}/><span>Railwise</span></div><div><small>BOOKING REFERENCE</small><strong>{ticket.reference}</strong></div></div>
    <div className="confirmation-route"><div><span className="eyebrow">FROM</span><h3>{ticket.origin.code}</h3><p>{ticket.origin.name}</p></div><ArrowRight size={25}/><div><span className="eyebrow">TO</span><h3>{ticket.destination.code}</h3><p>{ticket.destination.name}</p></div><div className="confirmation-journey"><strong>{ticket.train}</strong><p>#{ticket.train_number}</p><span>{new Date(`${ticket.journey_date}T12:00:00`).toLocaleDateString('en-IN',{day:'numeric',month:'long',year:'numeric'})}</span></div></div>
    <div className="confirmation-schedule"><div><small>DEPARTURE</small><strong>{clockTime(ticket.departure_at)} IST</strong><span>{ticket.departure_at?journeyDate(ticket.departure_at):journeyDate(ticket.journey_date)}</span></div><div><small>JOURNEY DURATION</small><strong>{durationText(ticket.duration_minutes)}</strong><span>{ticket.class_name||classNames[booking.allocated_class||booking.travel_class]||booking.travel_class}</span></div><div><small>ARRIVAL</small><strong>{clockTime(ticket.arrival_at)} IST</strong><span>{ticket.arrival_at?journeyDate(ticket.arrival_at):'Date unavailable'}</span></div><p>Booked on: {dateTime(ticket.booked_at)}</p></div><div className="confirmation-section-title"><Users size={17}/><h3>Passenger & seat details</h3><span>{ticket.passengers.length} reserved seat{ticket.passengers.length===1?'':'s'}</span></div><div className="confirmed-passengers">{ticket.passengers.map((p,i)=><article className="confirmed-passenger" key={i}><div className="confirmed-person"><span className="confirmation-person-number">{i+1}</span><div><h4>{displayName(p.name)}</h4><p>{p.age} years · {p.gender}</p></div><span className="confirmed-label"><CheckCircle2 size={16}/> Confirmed</span></div><div className="confirmed-allocation"><div><span>COACH</span><strong>{p.coach}</strong></div><div><span>SEAT / BERTH</span><strong>{p.seat_number}</strong></div><div><span>BERTH TYPE</span><strong>{berthLabels[p.berth_type||'NA']}</strong></div></div><div className="confirmed-passenger-fare"><span>Passenger fare</span><strong>{money(p.fare)}</strong></div></article>)}</div>
    <div className="confirmation-bottom"><div className="confirmation-payment"><div className="confirmation-section-title"><CreditCard size={17}/><h3>Payment details</h3></div><dl><div><dt>Provider / status</dt><dd>{ticket.payment.provider} · Captured</dd></div><div><dt>Payment method</dt><dd>{ticket.payment.method?({upi:'UPI',card:'Card',netbanking:'Net banking',wallet:'Wallet'}[ticket.payment.method]||ticket.payment.method):'Not recorded'}</dd></div><div><dt>Order ID</dt><dd>{ticket.payment.order_id}</dd></div><div><dt>{ticket.payment.captured_at?'Payment verified':'Payment recorded'}</dt><dd>{dateTime(ticket.payment.captured_at||ticket.payment.recorded_at)}</dd></div></dl><p>Booking contact</p><strong>{ticket.contact.email}</strong><span>{ticket.contact.phone}</span></div><aside className="confirmation-total"><span className="eyebrow">FARE SUMMARY</span><dl><div><dt>Passenger fares</dt><dd>{money(ticket.fare.base_fare)}</dd></div><div><dt>Booking fee</dt><dd>{money(ticket.fare.booking_fee)}</dd></div><div className="confirmation-paid"><dt>Total paid</dt><dd>{money(ticket.fare.total)}</dd></div></dl><p>Sample project pricing. No official railway tariff or real PNR is supplied.</p></aside></div>
    <div className="confirmation-ticket-footer"><span>{ticket.reference} · Confirmed booking snapshot</span><span>Downloaded tickets do not update after cancellation.</span></div></div>
    <div className="confirmation-actions"><p><ShieldCheck size={15}/> Your PDF is generated from the server’s verified booking record.</p><button className="secondary" disabled={downloading} onClick={download}><Download size={15}/> Download demo ticket</button></div>
    {notice&&<p className="confirmation-download-notice" role="status">{notice}</p>}
    </>}
    <div className="confirmation-actions"><button type="button" className="danger-outline" onClick={()=>setCancelling(true)}>Cancel booking</button></div>
    {cancelling&&<CancellationDialog booking={booking} onUpdated={onUpdated} onClose={()=>setCancelling(false)}/>}
    <PaymentStatus booking={booking} onUpdated={onUpdated}/>
  </section>;
}
