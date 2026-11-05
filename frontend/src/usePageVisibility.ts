import {useSyncExternalStore} from 'react';

export function pageIsVisible() { return !document.hidden; }
export function subscribeVisibility(changed: () => void) {
  document.addEventListener('visibilitychange', changed);
  return () => document.removeEventListener('visibilitychange', changed);
}

export default function usePageVisibility() {
  return useSyncExternalStore(subscribeVisibility, pageIsVisible, () => true);
}
