import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'vite';
import {renderToStaticMarkup} from 'react-dom/server';
import {createElement} from 'react';

test('unpaid review shows preference but never provisional coach or berth allocation',async()=>{
 const server=await createServer({cacheDir:'node_modules/.vite-tests-booking-review',server:{middlewareMode:true,hmr:false,ws:false},appType:'custom'});
 try{
  const {default:Checkout}=await server.ssrLoadModule('/src/components/BookingCheckout.tsx');
  const booking={booking_id:123,status:'PENDING',train:'Example Express',date:'2026-10-23',origin:'PNBE',destination:'HWH',expires_at:new Date(Date.now()+600000).toISOString(),contact_email:'test@example.invalid',contact_phone:'9999999999',travel_class:'1A',quota:'GN',seat:'H1-99',passengers:[{booking_id:123,name:'Example Passenger',age:25,gender:'Male',country:'India',seat:'H1-99',allocated_berth:'UB',berth_preference:'LB',fare:'1918.50'}],payment_attempts:[],refunds:[],email_notifications:[],fare_details:{},fare_breakdown:{total:'1918.50',booking_fee:'0',label:'Project fare'}};
  const html=renderToStaticMarkup(createElement(Checkout,{initialBooking:booking,onUpdated:()=>{}}));
  assert.ok(html.includes('Lower'));
  assert.ok(html.includes('Coach &amp; berth details after confirmation'));
  assert.ok(!html.includes('H1-99'));
  assert.ok(!html.includes('Upper'));
  assert.ok(html.includes('1,918.50'));
  assert.ok(html.includes('Cancel booking'));
  assert.ok(!html.includes('Release all seats'));
  assert.ok(!html.includes('allotted berths and the total fare'));
  const cancelled=renderToStaticMarkup(createElement(Checkout,{initialBooking:{...booking,status:'CANCELLED'},onUpdated:()=>{}}));
  assert.ok(cancelled.includes('Your seats have been released.'));
  assert.ok(!cancelled.includes('with Razorpay'));
  assert.ok(!cancelled.includes('Cancel booking'));
 }finally{await server.close();}
});
