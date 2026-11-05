// Set the public Render origin on Vercel; local development keeps Vite's proxy.
export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
