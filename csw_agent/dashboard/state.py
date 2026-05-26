"""Shared dashboard state: settings, CSW client, optional cache."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from csw_agent.cache import TTLCache
from csw_agent.config import Settings

if TYPE_CHECKING:
    from csw_agent.client import CSWClient

logger = logging.getLogger(__name__)


@dataclass
class DashboardState:
    """Holds the live CSW client (if connected) plus cached aggregates."""

    settings: Settings
    client: CSWClient | None = None
    overview_cache: TTLCache = field(init=False)
    versions_cache: TTLCache = field(init=False)
    workspaces_cache: TTLCache = field(init=False)

    def __post_init__(self) -> None:
        self.overview_cache = TTLCache(self.settings.workspace_cache_ttl_seconds)
        self.versions_cache = TTLCache(self.settings.workspace_cache_ttl_seconds)
        self.workspaces_cache = TTLCache(self.settings.workspace_cache_ttl_seconds)

    @property
    def csw_connected(self) -> bool:
        return self.client is not None


def build_state(settings: Settings) -> DashboardState:
    """Construct the dashboard state, attempting to connect to CSW lazily."""
    state = DashboardState(settings=settings)
    try:
        from csw_agent.client import CSWClient

        client = CSWClient(settings)
        if client.health_check():
            state.client = client
        else:
            logger.warning("CSW health check failed; dashboard will operate in offline mode.")
    except FileNotFoundError as exc:
        logger.warning("CSW credentials missing: %s", exc)
    except Exception as exc:
        logger.warning("Could not initialize CSW client: %s", exc)
    return state
