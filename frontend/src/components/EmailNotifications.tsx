import { Mail, CheckCircle2, Clock3 } from 'lucide-react';
import type { Booking } from '../api';
import {maskEmail,dateTime} from '../bookingDisplay';
const labels:Record<string,string>={QUEUED:'Your email update is being prepared',WAITING_VERIFICATION:'Verify your account email to receive this update',RETRY:'We’ll try sending this email again shortly',FAILED:'We couldn’t send this email. Your booking details are available here.',SKIPPED:'A newer update is available'};
const events:Record<string,string>={PROMOTED:'Waitlist update',CONFIRMED:'Confirmation',CANCELLED:'Cancellation',REFUND_REQUESTED:'Refund request',REFUND_PROCESSING:'Refund progress',REFUND_PROCESSED:'Refund processed',REFUND_FAILED:'Refund update',REFUND_UNKNOWN:'Refund update',REFUND_REVIEW:'Refund update'};
export default function EmailNotifications({booking}:{booking:Booking}) {
 const items=booking.email_notifications||[];
 if(!items.length)return null;
 return <section className="booking-emails" aria-label="Booking email notifications"><h3><Mail size={18}/> Email updates</h3><ul>{items.map(n=>{
  const sent=n.state==='SENT'&&n.delivery_channel==='smtp';const title=events[n.kind]||'Booking';
  return <li key={n.id}>{sent?<CheckCircle2 size={18}/>:<Clock3 size={18}/>}<div><strong>{sent?`${title} email sent${n.recipient?' to '+maskEmail(n.recipient):''}`:title+' email'}</strong><p>{sent?(n.sent_at?dateTime(n.sent_at):'Sent'):n.state==='SENT'?'Your email update is prepared. You can view all booking details here.':labels[n.state]||'Your email update is pending'}</p></div></li>;
 })}</ul></section>;
}
