import type { ResultFilters as Filters } from '../results';
export default function ResultFilters({value,onChange,onReset}:{value:Filters;onChange:(value:Filters)=>void;onReset:()=>void}) {
  const set=(field:keyof Filters,next:string)=>onChange({...value,[field]:next});
  return <section className="result-filters" aria-label="Filter and sort trains">
    <div className="filter-heading"><h3>Find your best journey</h3><button type="button" className="text-button" onClick={onReset}>Reset filters</button></div>
    <div className="filter-grid">
      <label>Departure time (IST)<select value={value.departure} onChange={e=>set('departure',e.target.value)}><option value="any">Any departure</option><option value="night">00:00–06:00</option><option value="morning">06:00–12:00</option><option value="afternoon">12:00–18:00</option><option value="evening">18:00–24:00</option></select></label>
      <label>Coach class<select value={value.travelClass} onChange={e=>set('travelClass',e.target.value)}><option value="any">All classes</option><option value="SL">Sleeper (SL)</option><option value="3A">AC 3 Tier (3A)</option><option value="2A">AC 2 Tier (2A)</option><option value="1A">AC First (1A)</option><option value="CC">Chair Car (CC)</option><option value="EC">Executive Chair (EC)</option></select></label>
      <label>Maximum fare per passenger<input type="number" min="0" step="1" placeholder="Any fare (₹)" value={value.maxFare} onChange={e=>set('maxFare',e.target.value)}/></label>
      <label>Maximum duration (hours)<input type="number" min="0" step="0.5" placeholder="Any duration" value={value.maxDuration} onChange={e=>set('maxDuration',e.target.value)}/></label>
      <label>Sort by<select value={value.sort} onChange={e=>set('sort',e.target.value)}><option value="departure-asc">Departure: earliest first</option><option value="departure-desc">Departure: latest first</option><option value="fare-asc">Fare: low to high</option><option value="fare-desc">Fare: high to low</option><option value="duration-asc">Duration: shortest first</option><option value="duration-desc">Duration: longest first</option></select></label>
    </div><p>Fares are per passenger, based on the lowest fare among the displayed classes. Times and duration use the actual boarding and arrival stations.</p>
  </section>;
}
