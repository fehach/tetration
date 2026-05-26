# CSW Agent Dashboard

Web front-end for the CSW agent. Allows users without a command line to:
- run **local queries** from the catalog (16 pre-built reports),
- **chat with Claude** via ClaudeGate, with generated code validated by the sandbox and executed live,
- manage the agent **configuration** (safe mode, etc.).

Vite + React + TypeScript + Tailwind, with the Cisco palette defined in [`CLAUDE.md`](../CLAUDE.md).

## Develop

```bash
cd dashboard
npm install
npm run dev      # http://localhost:5173 — proxies /api → http://127.0.0.1:8765
```

In another terminal start the backend:

```bash
csw-agent dashboard         # http://127.0.0.1:8765
```

## Build

```bash
npm run build                       # emits to ../csw_agent/dashboard/static
```

After building, `csw-agent dashboard` serves the SPA from `/` and the API from `/api/*`.

## Stack

- React 18 + TypeScript
- Vite
- Tailwind CSS (Cisco palette in `tailwind.config.ts`)
- Lucide React icons
- React Router (Home · Queries · Chat · Configuration)

## Pages

| Page | Description |
|---|---|
| **Home** | Welcome screen with quick-access shortcuts and connection status |
| **Queries** | Catalog of 16 local reports grouped by category. Each card includes the required inputs and a Run button. Results are shown inline (native table for structured reports, monospaced for others), with CSV download when available |
| **Chat with Claude** | Natural language conversation. SSE streams: text → generated code → sandbox result (passed/blocked) → captured output |
| **Configuration** | Safe mode toggle + read-only data (endpoint, credentials, model, ClaudeGate URL, TLS) |
