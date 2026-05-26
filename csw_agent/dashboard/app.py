"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from csw_agent import __version__
from csw_agent.config import Settings
from csw_agent.dashboard.chat_api import session as chat_session
from csw_agent.dashboard.chat_api import stream_chat
from csw_agent.dashboard.prompt_history import get_history
from csw_agent.dashboard.queries_api import build_web_catalog, execute_query
from csw_agent.dashboard.state import DashboardState, build_state
from csw_agent.queries import QueryContext

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_FILE_SUFFIXES = (".csv",)


class ChatRequest(BaseModel):
    message: str


class ConfigPatch(BaseModel):
    safe_mode: bool | None = None


class QueryRunRequest(BaseModel):
    inputs: dict[str, Any] = {}


def create_app(settings: Settings, state: DashboardState | None = None) -> FastAPI:
    """Build the FastAPI app. ``state`` is injected for tests."""
    app = FastAPI(title="CSW Agent Dashboard", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state = state or build_state(settings)
    catalog = build_web_catalog()
    catalog_by_key = {q.key: q for q in catalog}
    ctx = QueryContext(client=state.client, settings=state.settings) if state.client else None

    _register_routes(app, state, catalog, catalog_by_key, ctx)
    _register_static(app)
    return app


def _register_routes(
    app: FastAPI,
    state: DashboardState,
    catalog: list,
    catalog_by_key: dict[str, Any],
    ctx: QueryContext | None,
) -> None:
    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "version": __version__,
            "csw_connected": state.csw_connected,
            "endpoint": state.settings.api_endpoint,
            "model": state.settings.claude_model,
            "claudegate_url": state.settings.claudegate_url,
            "safe_mode": state.settings.safe_mode,
        }

    @app.get("/api/queries")
    def list_queries() -> list[dict[str, Any]]:
        return [q.to_dict() for q in catalog]

    @app.post("/api/queries/{key}/run")
    def run_query(key: str, body: QueryRunRequest) -> dict[str, Any]:
        query = catalog_by_key.get(key)
        if query is None:
            raise HTTPException(status_code=404, detail=f"Unknown query: {key}")
        if query.needs_csw and ctx is None:
            raise HTTPException(status_code=503, detail="CSW client not available")
        missing = [i.name for i in query.inputs if i.required and not body.inputs.get(i.name)]
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing required inputs: {missing}")
        assert ctx is not None
        return execute_query(query, ctx, body.inputs)

    @app.get("/api/files/{filename}")
    def download_file(filename: str) -> FileResponse:
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        if not filename.endswith(ALLOWED_FILE_SUFFIXES):
            raise HTTPException(status_code=400, detail="Unsupported file type")
        path = Path.cwd() / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path, media_type="text/csv", filename=filename)

    @app.post("/api/chat")
    async def chat(req: ChatRequest) -> StreamingResponse:
        if not req.message.strip():
            raise HTTPException(status_code=422, detail="Empty message")
        return StreamingResponse(stream_chat(state, req.message), media_type="text/event-stream")

    @app.post("/api/chat/reset")
    def chat_reset() -> dict[str, bool]:
        chat_session().reset()
        return {"ok": True}

    @app.get("/api/chat/history")
    def chat_history() -> list[dict[str, str]]:
        return list(chat_session().history)

    @app.get("/api/chat/prompts")
    def list_prompts(limit: int = 50) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in get_history().list(limit=limit)]

    @app.delete("/api/chat/prompts")
    def clear_prompts() -> dict[str, bool]:
        get_history().clear()
        return {"ok": True}

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        s = state.settings
        return {
            "api_endpoint": s.api_endpoint,
            "credentials_file": str(s.credentials_file),
            "claude_model": s.claude_model,
            "claudegate_url": s.claudegate_url,
            "safe_mode": s.safe_mode,
            "verify_tls": s.verify_tls,
            "log_level": s.log_level,
        }

    @app.patch("/api/config")
    def patch_config(patch: ConfigPatch) -> dict[str, Any]:
        if patch.safe_mode is not None:
            state.settings.safe_mode = patch.safe_mode
        return {"safe_mode": state.settings.safe_mode}


def _register_static(app: FastAPI) -> None:
    if not STATIC_DIR.exists():
        return
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(index_file)

        @app.get("/{path:path}")
        def spa_fallback(path: str) -> FileResponse:
            candidate = STATIC_DIR / path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_file)
