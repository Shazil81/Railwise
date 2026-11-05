import {useEffect,useRef} from 'react';
import type {ReactNode} from 'react';
import {X} from 'lucide-react';

export default function AuthDialog({label,onClose,children}:{label:string;onClose:()=>void;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null);
 const previousFocus=useRef(document.activeElement as HTMLElement|null);
 useEffect(()=>{
  const dialog=ref.current!,previous=previousFocus.current,overflow=document.body.style.overflow;
  dialog.showModal();document.body.style.overflow='hidden';
  return()=>{dialog.close();document.body.style.overflow=overflow;queueMicrotask(()=>previous?.focus());};
 },[]);
 return <dialog ref={ref} className="auth-surface" aria-label={label} onCancel={event=>{event.preventDefault();onClose();}}><button type="button" className="auth-close" aria-label="Close account dialog" onClick={onClose}><X size={20}/></button>{children}</dialog>;
}
