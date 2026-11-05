import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';
import { X } from 'lucide-react';
import './BookingDialog.css';

export default function BookingDialog({title,onClose,children,className=''}:{title:string;onClose:()=>void;children:ReactNode;className?:string}) {
  const ref=useRef<HTMLDialogElement>(null),titleId=useId();
  useEffect(()=>{
    const dialog=ref.current!,previous=document.activeElement as HTMLElement|null;
    dialog.showModal();
    const original=document.body.style.overflow;document.body.style.overflow='hidden';
    dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    return()=>{dialog.close();document.body.style.overflow=original;previous?.focus();};
  },[]);
  return <dialog ref={ref} className={`booking-dialog ${className}`} aria-labelledby={titleId} onCancel={event=>{event.preventDefault();onClose();}}>
    <div className="booking-dialog-heading"><h2 id={titleId}>{title}</h2><button type="button" className="dialog-close" aria-label="Close dialog" onClick={onClose}><X size={20}/></button></div>{children}
  </dialog>;
}
