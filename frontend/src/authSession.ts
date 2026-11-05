// Authentication lasts only for this loaded page. A refresh starts as a guest.
export function createAuthSession() {
  let user: { token: string | null; username: string | null } = { token: null, username: null };
  return {
    read: () => ({ ...user }),
    set: (token: string, username: string) => { user = { token, username }; },
    clear: () => { user = { token: null, username: null }; },
  };
}

export function clearLegacyLogin(storage: Pick<Storage, 'removeItem'>) {
  // Storage may be blocked by browser privacy settings; guest search still works.
  try { storage.removeItem('token'); storage.removeItem('username'); } catch { /* No persistent login is read. */ }
}

export const authSession = createAuthSession();
if (typeof window !== 'undefined') {
  try { clearLegacyLogin(window.localStorage); } catch { /* Storage access can be disabled. */ }
}
