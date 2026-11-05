import { useEffect, useId, useState } from 'react';
import { MapPin } from 'lucide-react';
import api, { errorMessage } from '../api';

interface Station { code: string; name: string }
interface Suggestion { query: string; rows: Station[]; message: string }
export default function StationInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [suggestion, setSuggestion] = useState<Suggestion>({ query: '', rows: [], message: '' });
  const query = value.trim();
  const ready = suggestion.query === query;
  const rows = ready ? suggestion.rows : [];
  useEffect(() => {
    if (open && active >= 0) document.getElementById(`${id}-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [active, id, open]);
  useEffect(() => {
    if (!open || query.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get<{ stations: Station[]; warning: string }>('/stations/search/', { params: { q: query }, signal: controller.signal });
        if (!controller.signal.aborted) setSuggestion({ query, rows: data.stations, message: data.warning });
      } catch (error) {
        if (!controller.signal.aborted) setSuggestion({ query, rows: [], message: errorMessage(error) });
      }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [open, query]);
  function select(station: Station) { onChange(`${station.name} (${station.code})`); setOpen(false); setActive(-1); }
  return <div className="station-input" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
    <label htmlFor={id}><span><MapPin size={14}/>{label}</span><input id={id} role="combobox" autoComplete="off" placeholder="City, station or code" value={value}
      aria-expanded={open} aria-autocomplete="list" aria-controls={`${id}-list`} aria-activedescendant={open && active >= 0 && rows[active] ? `${id}-${active}` : undefined}
      onFocus={() => setOpen(true)} onChange={e => { onChange(e.target.value); setOpen(true); setActive(-1); }}
      onKeyDown={e => {
        if (e.key === 'Escape') { setOpen(false); e.preventDefault(); }
        if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(i => Math.min(i + 1, rows.length - 1)); }
        if (e.key === 'ArrowUp') { e.preventDefault(); setActive(i => Math.max(i - 1, 0)); }
        if (e.key === 'Enter' && open && active >= 0 && rows[active]) { e.preventDefault(); select(rows[active]); }
      }}/></label>
    {open && <div className="station-suggestions"><ul id={`${id}-list`} role="listbox" aria-label={`${label} stations`}>
      {rows.map((s, index) => <li role="option" aria-selected={index === active} id={`${id}-${index}`} key={s.code} onMouseDown={e => e.preventDefault()} onClick={() => select(s)}><span>{s.name}</span><strong>{s.code}</strong></li>)}
    </ul><p role="status">{query.length < 2 ? 'Type at least 2 letters, or enter a station code.' : !ready ? 'Finding stations…' : suggestion.message || (!rows.length ? 'No matching stations. Try a station code.' : 'Choose a station, or continue typing to narrow results.')}</p></div>}
  </div>;
}
