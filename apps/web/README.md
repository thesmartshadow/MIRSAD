# MIRSAD Web

React, TypeScript, and Vite frontend for MIRSAD. The interface uses shadcn/ui exclusively, Tailwind design tokens, shadcn Charts, local IBM Plex fonts, and root-level Arabic/English direction handling.

Run commands from the repository root:

```bash
npm run dev:web
npm run test:web
npm run typecheck
npm run build
```

During development, Vite proxies `/api` to `http://127.0.0.1:8000`. Override the API root for a static build with `VITE_API_ROOT` if required.
