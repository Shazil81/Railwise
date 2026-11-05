export interface AccountAction { purpose: 'verify' | 'reset'; token?: string }
export function readAccountAction(): AccountAction | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const purpose = params.get('account_action');
  const token = params.get('token');
  if ((purpose === 'verify' || purpose === 'reset') && token) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    return {purpose, token};
  }
  return null;
}
