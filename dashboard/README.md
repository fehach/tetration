# CSW Agent Dashboard

Front-end web del agente CSW. Permite a usuarios sin línea de comandos:
- ejecutar **consultas locales** del catálogo (16 informes pre-construidos),
- **conversar con Claude** vía ClaudeGate, con código generado, validado por sandbox y ejecutado en vivo,
- gestionar la **configuración** del agente (modo seguro, etc.).

Vite + React + TypeScript + Tailwind, con paleta Cisco definida en [`CLAUDE.md`](../CLAUDE.md).

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
- Tailwind CSS (paleta Cisco en `tailwind.config.ts`)
- Lucide React icons
- React Router (Inicio · Consultas · Chat · Configuración)

## Páginas

| Página | Para qué sirve |
|---|---|
| **Inicio** | Bienvenida con accesos rápidos y estado de conexión |
| **Consultas** | Catálogo de 16 informes locales, agrupados por categoría. Cada card incluye los inputs necesarios y un botón Ejecutar. El resultado se muestra inline (tabla nativa para informes estructurados, monoespaciado para los demás), con descarga de CSVs cuando aplica |
| **Chat con Claude** | Conversación en lenguaje natural. SSE muestra: texto en streaming → código generado → resultado del sandbox (aprobado/bloqueado) → salida capturada al ejecutar |
| **Configuración** | Toggle de modo seguro + datos solo-lectura (endpoint, credenciales, modelo, ClaudeGate URL, TLS) |
