import {clearPassengerDrafts} from './passengerDraft.ts';
import axios from 'axios';
import { authSession } from './authSession.ts';

const api = axios.create({ baseURL: '/api', timeout: 15000 });

api.interceptors.request.use(config => {
  const token = authSession.read().token;
  // Public railway lookup must work even when a saved login token has expired.
  const publicRailwayLookup = /^\/(stations\/search\/|trains\/|journeys\/\d+\/(?:$|(?:quote|availability)\/))/.test(config.url || '');
  if (token && !publicRailwayLookup) config.headers.Authorization = `Token ${token}`;
  return config;
});

export function errorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) return error instanceof Error ? error.message : 'Something went wrong.';
  if (!error.response) return 'Cannot reach the booking service. Please try again.';
  if (error.response.status === 401 || error.response.status === 403) return 'Please sign in again to continue.';
  const data = error.response.data;
  if (typeof data === 'string') return 'The booking service could not complete this request.';
  const flatten = (value: unknown): string[] => typeof value === 'string' ? [value] : value && typeof value === 'object' ? Object.values(value).flatMap(flatten) : [];
  return flatten(data).join(' ') || 'The request could not be completed.';
}

export async function login(username: string, password: string) {
  const { data } = await api.post('/token/', { username, password });
  authSession.set(data.token, username);
  return data.token;
}

export async function register(username: string, email: string, password: string, password_confirm: string) {
  const { data } = await api.post('/accounts/signup/', { username, email, password, password_confirm });
  authSession.set(data.token, data.username);
}

export async function requestAccountLink(purpose: 'verify' | 'reset', username: string, email: string) {
  const { data } = await api.post(purpose === 'verify' ? '/accounts/request-verification/' : '/accounts/forgot-password/', { username, email });
  return data.detail as string;
}
export async function consumeAccountLink(purpose: 'verify' | 'reset', token: string, password: string, password_confirm: string) {
  const { data } = await api.post(purpose === 'verify' ? '/accounts/verify-email/' : '/accounts/reset-password/', { token, password, password_confirm });
  if (purpose === 'reset') { authSession.clear(); clearPassengerDrafts(); }
  return data.detail as string;
}
export async function getAccountStatus(): Promise<{username: string; email: string; email_verified: boolean}> {
  return (await api.get('/accounts/me/')).data;
}

export async function logout() {
  try { await api.post('/accounts/logout/'); }
  catch (error) {
    if (!axios.isAxiosError(error) || error.response?.status !== 401) throw error;
  }
  authSession.clear();
  clearPassengerDrafts();
}

export function getStoredUser() {
  return authSession.read();
}

export interface Stop {
  sequence: number;
  name: string;
  code: string;
  distance_km: number | null; arrival: string; departure: string; day: number;
}
export interface FareQuote {
  booking_open?: boolean; booking_error?: string;
  travel_class: string; class_name: string; quota: string; distance_km: number;
  base_fare: string; reservation_fee: string; demand_surcharge: string; tatkal_surcharge: string;
  total: string; available_seats: number; capacity: number; label: string;
}

export interface Journey {
  origin_code?: string; destination_code?: string; boarding_date?: string; nearby_match?: boolean;
  id: number;
  date: string;
  train: string;
  number: string;
  stops: Stop[];
  classes: FareQuote[];
}

export interface Passenger {
  coach?: string | null; seat_number?: number | null;
  country?:string;berth_preference?:string;allocated_berth?:string|null;allocated_class?:string|null;berth_preference_met?:boolean;
  booking_id: number; seat: string | null; name: string; age: number | null; gender: string; fare: string;
}
export interface PaymentAttempt {
  method?:string|null;created_at?:string;provider_created_at?:string|null;captured_at?:string|null;
  payment_id: string; state: string; amount: string; message: string; updated_at: string;
}
export interface RefundRecord {
  created_at?:string;processed_at?:string|null;
  reference: number; provider_id: string | null; payment_id: string; state: string;
  amount: string; reason: string; message: string; updated_at: string;
}
export interface Booking {
  booked_at?:string;departure_at?:string|null;arrival_at?:string|null;duration_minutes?:number|null;
  origin_code?:string|null;destination_code?:string|null;class_name?:string;payment_mode?:string;
  preferred_coach?:string;gstin?:string;confirmed_berths_only:boolean;consider_auto_upgrade:boolean;allocated_class:string|null;
  travel_class: string; quota: string; fare_details: Partial<FareQuote>;
  email_notifications: {id:number;kind:string;state:string;attempts:number;recipient:string;created_at:string;sent_at:string|null;message:string;delivery_channel?:string}[];
  booking_id: number;
  booking_reference: string;
  ticket_available: boolean;
  payment_attempts: PaymentAttempt[];
  refunds: RefundRecord[];
  payment_checked_at: string | null;
  status: string;
  amount: number;
  passengers: Passenger[];
  contact_email: string;
  contact_phone: string;
  reviewed_at: string | null;
  fare_breakdown: { passenger_count: number; base_fare: string; booking_fee: string; total: string; currency: string; label: string };
  razorpay_order_id?: string | null;
  razorpay_payment_id?: string | null;
  expires_at: string | null;
  seat: string | null;
  train: string;
  train_number: string;
  date: string;
  origin: string;
  destination: string;
  position: number | null;
}

export interface RazorpayOrder {
  order_id: string;
  amount: number;
  currency: string;
  key_id: string;
  booking_id: number;
  train: string;
  train_number: string;
  seat: string | null;
  user_name: string;
  user_email: string;
  user_phone: string;
}

export interface RazorpayPaymentResponse {
  razorpay_payment_id: string;
  razorpay_order_id: string;
  razorpay_signature: string;
}

export interface Confirmation {
  departure_at?:string|null;arrival_at?:string|null;duration_minutes?:number|null;class_name?:string;
  reference: string; booking_id: number; status: string; issued_at: string; booked_at: string;
  train: string; train_number: string; journey_date: string;
  origin: {name: string; code: string}; destination: {name: string; code: string};
  passengers: {name: string; age: number; gender: string; coach: string; seat_number: number; berth_type?: string; berth_preference?: string; fare: string}[];
  contact: {email: string; phone: string};
  fare: {base_fare: string; booking_fee: string; total: string; currency: string};
  payment: {provider: string; status: string; payment_id: string; order_id: string; amount: string; currency: string; recorded_at: string;method?:string|null;captured_at?:string|null};
  notice: string;
}
export async function getConfirmation(id: number) { return (await api.get<Confirmation>(`/bookings/${id}/confirmation/`)).data; }
export async function downloadTicket(id: number) {
  try {
    const response = await api.get<Blob>(`/bookings/${id}/ticket.pdf`, { responseType: 'blob' });
    if (!String(response.headers['content-type'] || '').includes('application/pdf')) throw new Error('Ticket service returned an unexpected response.');
    const url = URL.createObjectURL(response.data);
    const link = document.createElement('a');
    link.href = url; link.download = `Railwise-RW-${String(id).padStart(8, '0')}.pdf`;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()); } catch { /* Preserve the safe service error. */ }
    }
    throw error;
  }
}

export async function getJourneys(criteria: {origin:string;destination:string;date:string;quota:string;includeNearby?:boolean}) {
  return (await api.get<{journeys:Journey[]}>('/trains/search/',{params:{from:criteria.origin,to:criteria.destination,date:criteria.date,quota:criteria.quota,include_nearby:criteria.includeNearby ?? true}})).data.journeys;
}
export async function getJourneyQuote(id:number,from:number,to:number,travel_class:string,quota:string) {
  return (await api.get<FareQuote>(`/journeys/${id}/quote/`,{params:{from,to,travel_class,quota}})).data;
}

export type NewPassenger = Pick<Passenger,'name'|'age'|'gender'|'berth_preference'|'country'>;
export async function getJourney(id:number) { return (await api.get<Journey>(`/journeys/${id}/`)).data; }
export async function bookAutomatically(body:{journey_id:number;from_seq:number;to_seq:number;travel_class:string;quota:string;passengers:NewPassenger[];contact_email:string;contact_phone:string;confirmed_berths_only:boolean;consider_auto_upgrade:boolean;preferred_coach?:string;gstin?:string}) {
  return (await api.post<Booking>('/bookings/automatic/',body)).data;
}

export async function getBookings() {
  return (await api.get<Booking[]>('/bookings/')).data;
}

export async function cancelBooking(id: number) {
  return (await api.post<Booking>(`/bookings/${id}/cancel/`)).data;
}

export interface CancellationPreview {can_cancel:boolean;reason:string;refund_estimate:string;currency:string;notice:string}
export async function getCancellationPreview(id:number) {
  return (await api.get<CancellationPreview>(`/bookings/${id}/cancel-preview/`)).data;
}

export async function getAvailability(id: number, from: number, to: number, travel_class?:string) {
  return (await api.get<{ id: number; label: string;berth_type?:string }[]>(`/journeys/${id}/availability/`, { params: { from, to, travel_class } })).data;
}

export async function bookSeat(journey_id: number, seat_id: number, from_seq: number, to_seq: number) {
  return (await api.post<Booking>('/bookings/', { journey_id, seat_id, from_seq, to_seq })).data;
}

export async function bookSeats(journey_id: number, seat_ids: number[], from_seq: number, to_seq: number, quota='GN',preferences={confirmed_berths_only:false,consider_auto_upgrade:false}) {
  return (await api.post<Booking>('/bookings/', { journey_id, seat_ids, from_seq, to_seq, quota,...preferences })).data;
}
export async function getBooking(id: number) { return (await api.get<Booking>(`/bookings/${id}/`)).data; }
export async function savePassengerDetails(id: number, passengers: Pick<Passenger, 'booking_id' | 'name' | 'age' | 'gender' | 'berth_preference' | 'country'>[], contact_email: string, contact_phone: string,preferences?:{confirmed_berths_only:boolean;consider_auto_upgrade:boolean;preferred_coach?:string;gstin?:string}) {
  return (await api.put<Booking>(`/bookings/${id}/passengers/`, { passengers, contact_email, contact_phone,...preferences })).data;
}
export async function recoverPayment(id: number) { return (await api.post<Booking>(`/bookings/${id}/recover-payment/`)).data; }
export async function acceptFareReview(id: number) { return (await api.post<Booking>(`/bookings/${id}/review/`)).data; }

export async function createRazorpayOrder(bookingId: number) {
  return (await api.post<RazorpayOrder>(`/bookings/${bookingId}/create-order/`)).data;
}

export async function verifyRazorpayPayment(bookingId: number, data: RazorpayPaymentResponse) {
  return (await api.post<Booking>(`/bookings/${bookingId}/verify-payment/`, data)).data;
}

interface RazorpayFailure { error?: { description?: string } }
interface RazorpayInstance {
  open(): void;
  on(event: 'payment.failed', handler: (response: RazorpayFailure) => void): void;
}
interface RazorpayOptions {
  key: string; amount: number; currency: string; name: string; description: string;
  image: string; order_id: string;
  handler: (response: RazorpayPaymentResponse) => Promise<void>;
  prefill: { name: string; email: string; contact: string };
  theme: { color: string };
  modal: { ondismiss: () => void };
}
declare global {
  interface Window { Razorpay?: new (options: RazorpayOptions) => RazorpayInstance }
}

export function openRazorpayCheckout(
  order: RazorpayOrder,
  onSuccess: (booking: Booking) => void,
  onError: (err: string) => void,
  onDismiss?: () => void
) {
  if (!window.Razorpay) {
    onError('Razorpay SDK failed to load. Please check your internet connection.');
    return;
  }

  const options = {
    key: order.key_id,
    amount: order.amount,
    currency: order.currency,
    name: 'Railwise',
    description: `Train #${order.train_number} ${order.train}`,
    image: '/favicon.svg',
    order_id: order.order_id,
    handler: async function (response: RazorpayPaymentResponse) {
      try {
        const confirmedBooking = await verifyRazorpayPayment(order.booking_id, response);
        onSuccess(confirmedBooking);
      } catch (err) {
        onError(errorMessage(err));
      }
    },
    prefill: {
      name: order.user_name,
      email: order.user_email,
      contact: order.user_phone,
    },
    theme: {
      color: '#0284c7',
    },
    modal: {
      ondismiss: function () {
        if (onDismiss) onDismiss();
      },
    },
  };

  const rzp = new window.Razorpay(options);
  rzp.on('payment.failed', function (response: RazorpayFailure) {
    onError(response?.error?.description || 'Payment failed. Please try again.');
  });
  rzp.open();
}

export async function joinWaitlist(journey_id: number, from_seq: number, to_seq: number, travel_class='SL',quota='GN',preferences={confirmed_berths_only:false,consider_auto_upgrade:false}) {
  return (await api.post<Booking>('/waitlist/', { journey_id, from_seq, to_seq, travel_class,quota,...preferences })).data;
}

export default api;
