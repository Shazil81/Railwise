import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import TerminalConfirmation from './TerminalConfirmation';
import { TrainFront } from 'lucide-react';
import ClassAvailability from './ClassAvailability';
import { getJourneyQuote } from '../api';
import type { Journey,FareQuote } from '../api';
import { journeyMetrics, durationLabel } from '../results';

export default function LocalJourneyCard({journey,origin,destination,date,quota,originLabel,destinationLabel,onQuoteUpdated,authenticated,onSignIn}:{authenticated:boolean;onSignIn:()=>void;journey:Journey;origin:string;destination:string;date:string;quota:string;originLabel?:string;destinationLabel?:string;onQuoteUpdated:(quote:FareQuote)=>void}) {
  const navigate=useNavigate();
  const [pendingClass,setPendingClass]=useState<string|null>(null);
  const quotes=journey.classes;
  const from=journey.stops.find(stop=>stop.code===(journey.origin_code||origin))!,to=journey.stops.find(stop=>stop.code===(journey.destination_code||destination))!;
  const duration=journeyMetrics(journey,origin,destination).duration;
  const distance=(to.distance_km||0)-(from.distance_km||0);
  return <article className="train-card"><div className="ticket-ribbon"><span>Saved timetable</span><strong>#{journey.number}</strong><span className="ribbon-note">{date}</span></div><div className="train-card-top"><div className="train-identity"><span className="train-card-icon"><TrainFront size={21}/></span><h3>{journey.train}</h3></div><span className="service-tag">{quota==='TQ'?'Tatkal':'General'} quota</span></div>{journey.nearby_match&&<p className="terminal-match">City terminal match · Board at <strong>{from.name} ({from.code})</strong> · Arrive at <strong>{to.name} ({to.code})</strong></p>}<div className="train-route"><div><strong>{from.departure||from.code}</strong><span>{from.name} ({from.code})</span></div><div className="route-line"><span>{durationLabel(duration)} · {distance} km · {to.sequence-from.sequence-1} stops</span><div><i/><b/><TrainFront size={16}/><b/><i/></div><small>All times IST</small></div><div className="destination"><strong>{to.arrival||to.code}</strong><span>{to.name} ({to.code}){to.day>from.day?` · +${to.day-from.day} day`:''}</span></div></div><ClassAvailability quotes={quotes} selected={pendingClass} onSelect={code=>{setPendingClass(code);if(!authenticated)onSignIn();}} onRefresh={async code=>onQuoteUpdated(await getJourneyQuote(journey.id,from.sequence,to.sequence,code,quota))}/><p className="inventory-caption">Fare per passenger · 10-minute holds</p>{authenticated&&pendingClass&&<TerminalConfirmation searchedFrom={originLabel||origin} searchedTo={destinationLabel||destination} actualFrom={`${from.name} (${from.code})`} actualTo={`${to.name} (${to.code})`} details={`${journey.train} · ${date} · ${pendingClass} · ${quota==='TQ'?'Tatkal':'General'}`} onBack={()=>setPendingClass(null)} onContinue={()=>{navigate(`/book/${journey.id}?${new URLSearchParams({from:String(from.sequence),to:String(to.sequence),class:pendingClass,quota})}`);setPendingClass(null);}}/>}</article>;
}
