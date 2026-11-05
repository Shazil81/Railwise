import { useEffect, useState } from 'react';
import DashboardPage from './pages/DashboardPage';
import LoginPage from './pages/LoginPage';
import { getStoredUser, logout, errorMessage } from './api';
import './App.css';
import AccountRecovery from './components/AccountRecovery';
import { readAccountAction } from './accountAction';
import type { AccountAction } from './accountAction';
import AccountEmailBanner from './components/AccountEmailBanner';
import { Routes, Route, useLocation } from 'react-router-dom';
import BookingPage from './pages/BookingPage';
import AuthDialog from './components/AuthDialog';
const initialAction = readAccountAction();
export default function App() {
  const location=useLocation();
  const [authenticated, setAuthenticated] = useState(Boolean(getStoredUser().token));
  const [signingIn, setSigningIn] = useState(false);
  const [authError, setAuthError] = useState('');
  const [action,setAction]=useState<AccountAction|null>(initialAction);
  const [accountVersion,setAccountVersion]=useState(0);
  useEffect(()=>{const changed=()=>{const next=readAccountAction();if(next)setAction(next);};window.addEventListener('hashchange',changed);return()=>window.removeEventListener('hashchange',changed);},[]);
  async function signOut() {
    setAuthError('');
    try { await logout(); setAuthenticated(false); }
    catch (error) { setAuthError(`Sign out failed: ${errorMessage(error)} Please retry.`); }
  }
  function closeRecovery(){setAction(null);setAuthenticated(Boolean(getStoredUser().token));setAccountVersion(v=>v+1);setSigningIn(true);}
  const mainId=location.pathname==='/'?'home-main':'booking-main';
  return <>
    <a className="skip-link" href={`#${mainId}`} onClick={event=>{event.preventDefault();const main=document.getElementById(mainId);main?.focus();main?.scrollIntoView({block:'start'});}}>Skip to main content</a>
    {authError&&<div className="error-box" role="alert">{authError}</div>}
    <div inert={signingIn||Boolean(action)}>
      {authenticated&&<AccountEmailBanner key={accountVersion} onVerify={()=>setAction({purpose:'verify'})}/>}
      <div hidden={location.pathname!=='/'}><DashboardPage authenticated={authenticated} onSignIn={()=>setSigningIn(true)} onSignOut={signOut}/></div>
      <Routes>
        <Route path="/book/:journeyId" element={<BookingPage authenticated={authenticated} onSignIn={()=>setSigningIn(true)}/>}/>
        <Route path="/booking/:bookingId" element={<BookingPage authenticated={authenticated} onSignIn={()=>setSigningIn(true)}/>}/>
        <Route path="*" element={null}/>
      </Routes>
    </div>
    {action?<AuthDialog label="Account recovery" onClose={closeRecovery}><AccountRecovery key={`${action.purpose}-${action.token||'request'}`} action={action} onClose={closeRecovery}/></AuthDialog>:signingIn&&<AuthDialog label="Railwise account" onClose={()=>setSigningIn(false)}><LoginPage onRecovery={purpose=>setAction({purpose})} onLogin={()=>{setAuthenticated(true);setSigningIn(false);setAuthError('');setAccountVersion(v=>v+1);}} onGuest={()=>setSigningIn(false)}/></AuthDialog>}
  </>;
}
