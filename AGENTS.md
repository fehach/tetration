# AGENTS.md — Project notes for AI/dev agents

## Verification commands

```bash
# Inside the project venv (`pip install -e ".[dev]"`):
ruff check .
ruff format --check .
mypy csw_agent
pytest
```

Run all four before declaring a task complete.

## Conventions

- Code in English; conversation/comments to humans in Spanish (per `CLAUDE.md`).
- Conventional commits: `feat(scope): …`, `fix(scope): …`, `refactor(scope): …`, etc.
- Functions ≤ 30 lines when reasonable.
- Add docstrings only when intent is non-obvious.
- Never refactor code unless explicitly asked.

## Credentials

Credentials live at `~/.csw/credentials.json` with `chmod 600`. They are NEVER committed.
`CSW_CREDENTIALS` overrides the default path. Legacy locations (`./credentials.json`,
`~/Downloads/cxtaas_api_credentials.json`) emit a warning when used.

## Sandbox

`csw_agent/ai/sandbox.py` validates Claude-generated code before `exec()`. When extending the
sandbox: prefer adding to `BANNED_BUILTINS` or shrinking `ALLOWED_IMPORTS`; never broaden them
without a corresponding test in `tests/test_sandbox.py`.

## Shared state

- `csw_agent.queries.QueryContext` is the only mutable container passed between the CLI and the
  query catalog. Avoid module-level globals.
- `ctx.workspace_cache` (TTL 5 min) memoizes the expensive hostname→workspace mapping.

## Dashboard

The web dashboard lives in two places:
- Backend: `csw_agent/dashboard/` (FastAPI). Launched via `csw-agent dashboard`.
- Frontend: `dashboard/` (Vite + React + TS). Build emits to `csw_agent/dashboard/static/`.

Telemetry is collected in `csw_agent/telemetry.py` (process-wide singleton). `CSWClient.call`
and `ClaudeRunner.stream` push events; the CLI wraps queries; `TelemetryLogHandler` mirrors
log records so they show up in the Activity page via SSE.

When adding a new dashboard route:
1. Add the endpoint to `csw_agent/dashboard/app.py` (use pure helpers in `aggregations.py`).
2. Type the response in `dashboard/src/api/types.ts` and add a method to `api/client.ts`.
3. Consume it via `usePolling` (REST) or `useLogStream`-style hooks (SSE).
4. Add a backend test to `tests/test_dashboard.py`.

## Adding a query

1. Add the function to the appropriate module in `csw_agent/queries/`.
2. Register it in `csw_agent/queries/__init__.py::build_registry`.
3. If it produces a CSV, set `ctx.last_generated_csv = filepath` so query 16 can chat about it.
4. Add a unit test to `tests/test_queries.py`.
