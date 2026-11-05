import { ArrowRight, MapPin } from 'lucide-react';
import BookingDialog from './BookingDialog';
export default function TerminalConfirmation({searchedFrom,searchedTo,actualFrom,actualTo,details,onBack,onContinue}:{searchedFrom:string;searchedTo:string;actualFrom:string;actualTo:string;details:string;onBack:()=>void;onContinue:()=>void}) {
  const changed=searchedFrom!==actualFrom||searchedTo!==actualTo;
  return <BookingDialog title="Please confirm the booking details" onClose={onBack} className="terminal-dialog">
    <p className="terminal-class">{details}</p><p className="terminal-caption">You searched for:</p>
    <div className="terminal-route"><MapPin size={31}/><div><strong>{searchedFrom}</strong><small>From</small></div><ArrowRight size={25}/><div><strong>{searchedTo}</strong><small>To</small></div></div>
    <p className="terminal-caption">You are booking for:</p><div className={`terminal-route ${changed?'is-actual':''}`}><MapPin size={31}/><div><strong>{actualFrom}</strong><small>Boarding station</small></div><ArrowRight size={25}/><div><strong>{actualTo}</strong><small>Arrival station</small></div></div>
    <p className="terminal-help">{changed?'This train uses a nearby city terminal. Make sure you can reach the boarding station shown above.':'The boarding and arrival stations match your search.'}</p><div className="dialog-actions"><button className="secondary" onClick={onBack}>Back</button><button className="primary" onClick={onContinue}>Continue Booking</button></div>
  </BookingDialog>;
}
