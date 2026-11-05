import { useEffect, useState } from 'react';
import { getAccountStatus, errorMessage } from '../api';
export default function AccountEmailBanner({onVerify}: {onVerify:()=>void}) {
  const [account,setAccount]=useState<Awaited<ReturnType<typeof getAccountStatus>>|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{let active=true;getAccountStatus().then(data=>{if(active)setAccount(data);}).catch(e=>{if(active)setError(errorMessage(e));});return()=>{active=false;};},[]);
  if(error)return <div className="account-email-banner" role="status">Account status: {error}</div>;
  if(!account)return null;
  return <div className="account-email-banner"><span>{account.email_verified?'Email verified':`Email not verified${account.email?' · '+account.email:''}. Verify to enable password recovery.`}</span>{!account.email_verified&&<button className="secondary" onClick={onVerify}>Verify email</button>}</div>;
}
