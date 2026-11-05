import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {renderToStaticMarkup} from 'react-dom/server';
import {createElement} from 'react';
test('booking card renders readable journey data, masked emails and one visible payment reference',async()=>{
 const server=await createServer({cacheDir:'node_modules/.vite-tests-booking-card',server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
 try{
  const {default:BookingCard}=await server.ssrLoadModule('/src/components/BookingCard.tsx');
  const {default:Emails}=await server.ssrLoadModule('/src/components/EmailNotifications.tsx');
  const booking={booking_id:7,booking_reference:'RW-00000007',status:'CONFIRMED',ticket_available:true,train:'JANSHATABDI EXP',train_number:'12019',date:'2026-10-25',booked_at:'2026-10-24T12:00:00+05:30',departure_at:'2026-10-25T23:25:00+05:30',arrival_at:'2026-10-26T06:30:00+05:30',duration_minutes:425,origin:'Patna',destination:'Howrah',class_name:'AC Chair Car',travel_class:'CC',quota:'GN',amount:678.4,passengers:[{booking_id:7,name:'ahsan',age:24,gender:'Male',seat:'C1-1',coach:'C1',seat_number:1,allocated_class:'CC',berth_preference:'ANY',fare:'678.40'}],payment_attempts:[{payment_id:'pay_fixture',amount:'678.40',state:'CAPTURED',method:'upi',captured_at:'2026-10-24T12:01:00+05:30'}],refunds:[],email_notifications:[{id:1,state:'SENT',kind:'CONFIRMED',recipient:'ahsan@gmail.com',delivery_channel:'smtp'}]};
  const html=renderToStaticMarkup(createElement(BookingCard,{booking,onView:()=>{},onUpdated:()=>{}}));const text=html.replace(/<[^>]*>/g,'');
  for(const value of ['₹678.40','Ahsan','12019','Journey date:','Booked on:','23:25','AC Chair Car · Coach C1 · Seat 1','UPI','a***@gmail.com','View ticket','Download PDF'])assert.ok(text.includes(value),value);
  assert.equal((text.match(/pay_fixture/g)||[]).length,1);
  assert.ok(!text.includes('Console mode'));assert.ok(!text.includes('backend acceptance'));assert.ok(!text.includes('ahsan@gmail.com'));
  const local=renderToStaticMarkup(createElement(Emails,{booking:{...booking,email_notifications:[{...booking.email_notifications[0],delivery_channel:'local'}]}}));
  assert.ok(!local.includes('email sent'));assert.ok(local.includes('update is prepared'));
 }finally{await server.close();}
});
