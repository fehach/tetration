"""uvicorn launcher for the dashboard subcommand."""

from __future__ import annotations

import logging

from csw_agent.config import Settings

logger = logging.getLogger(__name__)


def run(settings: Settings, *, host: str = "127.0.0.1", port: int = 8765, reload: bool = False) -> int:
    try:
        import uvicorn
    except ImportError:
        print("  ✗ FastAPI/uvicorn not installed. Run: pip install 'csw-agent[dashboard]'")
        return 1

    from csw_agent.dashboard.app import create_app

    app = create_app(settings)
    print(f"  ✓ Dashboard ready at http://{host}:{port}")
    print("  Press Ctrl+C to stop.")
    uvicorn.run(app, host=host, port=port, reload=reload, log_level=settings.log_level.lower())
    return 0
