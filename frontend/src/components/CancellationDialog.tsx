import {useEffect,useState} from 'react';
import {AlertTriangle} from 'lucide-react';
import BookingDialog from './BookingDialog';
import {getCancellationPreview,errorMessage,cancelBooking} from '../api';
import type {Booking,CancellationPreview} from '../api';
import {formatMoney,journeyDate} from '../bookingDisplay';

export default function CancellationDialog({booking,onClose,onUpdated}:{booking:Booking;onClose:()=>void;onUpdated:(booking:Booking)=>void}){
 const [preview,setPreview]=useState<CancellationPreview|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{let active=true;getCancellationPreview(booking.booking_id).then(data=>{if(active)setPreview(data);}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[booking.booking_id]);
 async function confirm(){if(!preview?.can_cancel||busy)return;setBusy(true);setError('');try{onUpdated(await cancelBooking(booking.booking_id));onClose();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 return <BookingDialog title="Cancel this booking?" onClose={()=>{if(!busy)onClose();}} className="cancellation-dialog"><div className="cancel-warning"><AlertTriangle size={23}/><p>This cancels {booking.passengers.length===1?'this passenger’s booking':`the booking for all ${booking.passengers.length} passengers`} and releases the reserved seats.</p></div><div className="cancel-journey"><strong>{booking.train} · #{booking.train_number}</strong><p>{booking.origin} → {booking.destination}</p><p>Journey date: {journeyDate(booking.date)}</p><small>{booking.booking_reference}</small></div>{!preview&&!error&&<p role="status">Checking cancellation eligibility and refund…</p>}{preview&&<><div className="cancel-estimate"><span>Estimated new refund</span><strong>{formatMoney(preview.refund_estimate)}</strong></div><p className="cancel-policy">{preview.notice}</p>{!preview.can_cancel&&<p role="status" className="error-box">{preview.reason}</p>}</>}{error&&<p role="alert" className="error-box">{error}</p>}<div className="cancel-dialog-actions"><button type="button" className="secondary" data-autofocus disabled={busy} onClick={onClose}>Keep booking</button><button type="button" className="danger-button" disabled={!preview?.can_cancel||busy} onClick={()=>void confirm()}>{busy?'Cancelling…':'Yes, cancel booking'}</button></div></BookingDialog>;
}
