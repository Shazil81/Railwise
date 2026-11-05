import { SlidersHorizontal, ChevronDown, Info } from 'lucide-react';
import './BookingPreferences.css';
export interface Preferences {confirmed_berths_only:boolean;consider_auto_upgrade:boolean;preferred_coach?:string;gstin?:string}
export default function BookingPreferences({value,onChange,disabled=false}:{value:Preferences;onChange:(value:Preferences)=>void;disabled?:boolean}) {
  return <details className="other-preferences" open><summary><span className="preference-icon"><SlidersHorizontal size={21}/></span>Other Preferences<ChevronDown size={21}/></summary>
    <fieldset disabled={disabled}><legend className="sr-only">Other Preferences</legend><div className="other-preferences-grid">
      <label className="preference-option"><input type="checkbox" checked={value.consider_auto_upgrade} onChange={e=>onChange({...value,consider_auto_upgrade:e.target.checked})}/><span>Consider for Auto Upgradation</span></label>
      <label className="preference-option"><input type="checkbox" checked={value.confirmed_berths_only} onChange={e=>onChange({...value,confirmed_berths_only:e.target.checked})}/><span>Book only if confirm berths are allotted.</span></label>
      <label className="preference-field"><span>Preferred Coach No. <Info size={15} aria-label="Coach preference is subject to availability"/></span><input aria-label="Preferred coach number" value={value.preferred_coach||''} onChange={e=>onChange({...value,preferred_coach:e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,5)})} maxLength={5} pattern="[A-Z][A-Z0-9]{0,4}" placeholder="e.g. S1 or B1"/><small>Optional · Subject to availability</small></label>
      <label className="preference-field gst-field"><span>GST Details (Optional)</span><input aria-label="GSTIN" value={value.gstin||''} onChange={e=>onChange({...value,gstin:e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,15)})} maxLength={15} pattern="[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]" placeholder="Enter 15-character GSTIN"/><small>Saved with your booking · This demo does not issue tax invoices</small></label>
    </div><p className="other-preferences-help">Upgradation may offer a higher class during waitlist promotion at no extra fare. Confirmed berths only prevents waitlisting. Berth and coach requests are subject to availability.</p></fieldset>
  </details>;
}
