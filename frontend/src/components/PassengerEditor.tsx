import { useState } from 'react';
import type { NewPassenger } from '../api';
import { berthOptions, berthLabels } from '../berths';
import BookingDialog from './BookingDialog';

export default function PassengerEditor({initial,travelClass,onClose,onSave}:{initial?:NewPassenger;travelClass:string;onClose:()=>void;onSave:(passenger:NewPassenger)=>void}) {
  const [value,setValue]=useState<NewPassenger>(initial||{name:'',age:null,gender:'',country:'India',berth_preference:'ANY'}),[error,setError]=useState('');
  function save(event:React.FormEvent) {
    event.preventDefault();const name=value.name.trim().replace(/\s+/g,' ');
    if(!/^[\p{L} .'-]+$/u.test(name)||name.length<2||!/[\p{L}]/u.test(name)){setError('Enter the passenger’s full name using letters, spaces, apostrophes or hyphens.');return;}
    if(!value.country?.trim()||!/^[\p{L} .'-]+$/u.test(value.country)){setError('Enter a valid country name.');return;}
    onSave({...value,name,country:value.country.trim()});
  }
  return <BookingDialog title={initial?'Edit Passenger':'Add Passenger'} onClose={onClose} className="passenger-editor"><form className="passenger-dialog-form" onSubmit={save}>
    <p>Enter details as shown on the passenger’s ID. Each passenger needs an individual berth in this demo.</p>{error&&<p className="error-box" role="alert">{error}</p>}
    <label className="full-width">Full Name as per Govt. ID<input aria-label="Passenger full name" data-autofocus required minLength={2} maxLength={100} placeholder="Enter full name" autoComplete="off" value={value.name} onChange={e=>setValue({...value,name:e.target.value})}/></label>
    <label>Age<input aria-label="Passenger age" type="number" min={1} max={120} required placeholder="Enter age" value={value.age??''} onChange={e=>setValue({...value,age:e.target.value?Number(e.target.value):null})}/></label>
    <label>Gender<select aria-label="Passenger gender" required value={value.gender} onChange={e=>setValue({...value,gender:e.target.value})}><option value="">Select</option>{['Female','Male','Other','Prefer not to say'].map(gender=><option key={gender}>{gender}</option>)}</select></label>
    <label className="full-width">Country<input aria-label="Passenger country" list="passenger-countries" required maxLength={80} value={value.country||''} onChange={e=>setValue({...value,country:e.target.value})}/><datalist id="passenger-countries">{['India','Bangladesh','Nepal','Bhutan','Sri Lanka','United Kingdom','United States','Canada','Australia','Germany','France','Singapore'].map(country=><option key={country}>{country}</option>)}</datalist></label>
    <label className="full-width">Berth Preference<select aria-label="Passenger berth preference" value={value.berth_preference||'ANY'} onChange={e=>setValue({...value,berth_preference:e.target.value})}>{berthOptions(travelClass).map(code=><option key={code} value={code}>{berthLabels[code]}</option>)}</select><small>Subject to availability. Coach and berth details appear after booking confirmation.</small></label>
    <div className="dialog-actions"><button type="button" className="secondary" onClick={onClose}>Cancel</button><button className="primary">{initial?'Save changes':'Add Passenger'}</button></div>
  </form></BookingDialog>;
}
