# Interface

React and Vite. It calls its own origin; `vite.config.ts` sends `/api` to the server on port 8000.

```bash
npm ci
npm run dev        # development, http://localhost:5173
npm run build && npx vite preview   # built, http://localhost:4173
npx vitest run     # unit tests
e2e/run.sh         # replay check end to end (needs uv and Playwright)
```
