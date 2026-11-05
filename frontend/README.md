# Frontend

React + TypeScript + Vite UI for Railwise. See the root README for backend setup and sample accounts.

```powershell
npm ci
npm run dev -- --host 127.0.0.1
npm run lint
npm run build
```

The development proxy routes `/api` to `http://127.0.0.1:8000` by default. Set `API_PROXY_TARGET` before starting Vite to use another local API. Production hosting must serve `/api` through the same origin or provide an equivalent reverse proxy.
