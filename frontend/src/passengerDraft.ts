import type {NewPassenger} from './api';
import type {Preferences} from './components/BookingPreferences';

export interface PassengerDraft {
  passengers: NewPassenger[];
  email: string;
  phone: string;
  preferences: Preferences;
}
const drafts = new Map<string, {value: PassengerDraft; expires: number}>();
const lifetime = 30 * 60 * 1000;
// Personal details stay in memory for this tab, never in browser storage.
export function readPassengerDraft(key: string): PassengerDraft | undefined {
  const draft = drafts.get(key);
  if (!draft || draft.expires <= Date.now()) { drafts.delete(key); return; }
  return structuredClone(draft.value);
}
export function savePassengerDraft(key: string, value: PassengerDraft) {
  drafts.set(key, {value: structuredClone(value), expires: Date.now() + lifetime});
}
export function clearPassengerDraft(key: string) { drafts.delete(key); }
export function clearPassengerDrafts() { drafts.clear(); }
