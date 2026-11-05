import { ArrowRight, MapPin, Search, ShieldCheck, Ticket } from 'lucide-react';

export default function HomeHero({onSearch}:{onSearch:()=>void}) {
  return <section className="home-hero" aria-labelledby="home-title">
    <div className="home-hero-copy">
      <h1 id="home-title">Your next journey starts here.</h1>
      <p>Compare trains. Find your next stop.</p>
      <div className="home-hero-actions"><button type="button" className="hero-search-cta" onClick={onSearch}>Find trains <ArrowRight size={18}/></button><span className="home-guest-note"><ShieldCheck size={16}/>Search freely. Sign in to book.</span></div>
    </div>
    <div className="home-rail-scene" aria-hidden="true">
      <span className="scene-sun"/><span className="scene-orbit"/>
      <svg viewBox="0 0 450 230" fill="none"><path d="M0 220L450 130M0 235L450 145" stroke="#8d9ee8" strokeWidth="5"/><path d="M55 208L60 221M110 197L115 210M165 186L170 199M220 175L225 188M275 164L280 177M330 153L335 166M385 142L390 155" stroke="#8d9ee8" strokeWidth="4"/><g transform="rotate(-11 230 140)"><path d="M40 80Q40 65 55 65H325Q375 65 400 130L405 157H40Z" fill="#f5f8ff"/><path d="M40 138H402V151H40Z" fill="#76d8c8"/><path d="M321 76Q353 78 377 115H324Z" fill="#263b78"/><rect x="63" y="84" width="42" height="33" rx="6" fill="#435b9c"/><rect x="117" y="84" width="42" height="33" rx="6" fill="#435b9c"/><rect x="171" y="84" width="42" height="33" rx="6" fill="#435b9c"/><rect x="225" y="84" width="42" height="33" rx="6" fill="#435b9c"/><path d="M40 157H396L382 172H57Z" fill="#b5c4e7"/><circle cx="93" cy="174" r="12" fill="#182953"/><circle cx="319" cy="174" r="12" fill="#182953"/><path d="M382 133H394" stroke="#ffe09a" strokeWidth="6" strokeLinecap="round"/></g></svg>
      <div className="home-art-ticket"><span><Ticket size={22}/> GOOD JOURNEYS START HERE</span><strong>Pick a place. Find your train.</strong><div><MapPin size={16}/> Your city <ArrowRight size={17}/> Your next stop</div></div>
    </div>
  </section>;
}

export function HomeHighlights() {
  return <section className="home-highlights" aria-label="Plan your booking"><article><span className="highlight-icon highlight-blue"><Search/></span><div><h2>Find your route</h2><p>Search by city, station name or station code.</p></div></article><article><span className="highlight-icon highlight-purple"><Ticket/></span><div><h2>Choose your comfort</h2><p>Compare departure times, class fares and available seats.</p></div></article><article><span className="highlight-icon highlight-green"><ShieldCheck/></span><div><h2>Book with clarity</h2><p>Add passengers, review the fare and continue to checkout.</p></div></article></section>;
}
