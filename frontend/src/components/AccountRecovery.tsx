import { useEffect, useRef, useState } from 'react';
import { consumeAccountLink, requestAccountLink, errorMessage } from '../api';
import '../pages/LoginPage.css';

import type { AccountAction } from '../accountAction';
export default function AccountRecovery({action, onClose}: {action:AccountAction; onClose:()=>void}) {
  const heading=useRef<HTMLHeadingElement>(null);
  useEffect(()=>{heading.current?.focus({preventScroll:true});heading.current?.closest('.auth-overlay')?.scrollTo(0,0);},[]);
  const [username,setUsername]=useState('');
  const [email,setEmail]=useState('');
  const [password,setPassword]=useState('');
  const [confirm,setConfirm]=useState('');
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const [error,setError]=useState('');
  const [done,setDone]=useState(false);
  const title=action.token ? (action.purpose==='verify'?'Verify your email':'Set a new password') : (action.purpose==='verify'?'Send verification email':'Forgot your password?');
  async function submit(e:React.FormEvent) {
    e.preventDefault(); setBusy(true);setError('');setMessage('');
    try {
      const result=action.token ? await consumeAccountLink(action.purpose,action.token,password,confirm) : await requestAccountLink(action.purpose,username,email);
      setMessage(result);setDone(true);setPassword('');setConfirm('');
    } catch(e){setError(errorMessage(e));} finally{setBusy(false);}
  }
  return <div className="login-page"><div className="login-container"><h1>Railwise</h1><form className="login-form" onSubmit={submit}><h2 ref={heading} tabIndex={-1}>{title}</h2>
    {!action.token&&<><p>{action.purpose==='reset'?'Enter your username and verified account email.':'Enter your username and account email. Only verify an account you created.'}</p><div className="input-group"><label htmlFor="recovery-user">Username</label><input id="recovery-user" value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" maxLength={150} required/></div><div className="input-group"><label htmlFor="recovery-email">Email</label><input id="recovery-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email" maxLength={254} required/></div></>}
    {action.token&&action.purpose==='verify'&&<p>Confirm that you requested this verification for your Railwise account.</p>}
    {action.token&&action.purpose==='reset'&&<><div className="input-group"><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} maxLength={128} required/></div><div className="input-group"><label htmlFor="repeat-password">Confirm new password</label><input id="repeat-password" type="password" autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} maxLength={128} required/></div><small>Use at least 8 characters. Reset signs out all existing token sessions.</small></>}
    {error&&<div className="login-error" role="alert">{error}</div>}{message&&<p role="status">{message}</p>}
    {!done&&<button className="login-btn" disabled={busy}>{busy?'Please wait…':action.token?(action.purpose==='verify'?'Verify email':'Reset password'):'Send email'}</button>}
    {error&&action.token&&<p>Expired or used link? Return to sign in and request a new email.</p>}
    <button className="guest-btn" type="button" disabled={busy} onClick={onClose}>Back to sign in</button>
  </form></div></div>;
}
