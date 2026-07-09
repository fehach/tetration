"""Dashboard glue for the PCI-DSS compliance assessment."""

from __future__ import annotations

import logging
from typing import Any

from csw_agent.dashboard.state import DashboardState
from csw_agent.queries import QueryContext
from csw_agent.queries._helpers import fetch_scopes
from csw_agent.queries.pci import assess_scope

logger = logging.getLogger(__name__)

# Scope names containing one of these tokens are surfaced as CDE suggestions.
SUGGEST_TOKENS = ("pci", "cde")


def list_scopes(state: DashboardState) -> list[dict[str, Any]]:
    """Return scope names for the CDE selector, suggested ones first (cached)."""

    def compute() -> list[dict[str, Any]]:
        assert state.client is not None
        scopes, error = fetch_scopes(state.client)
        if error:
            raise RuntimeError(f"Could not list scopes: {error}")
        names = sorted({s.get("name", "") for s in scopes if s.get("name")})
        entries = [
            {"name": name, "suggested": any(token in name.lower() for token in SUGGEST_TOKENS)}
            for name in names
        ]
        entries.sort(key=lambda e: (not e["suggested"], e["name"]))
        return entries

    return state.scopes_cache.get_or_compute(compute)


def run_assessment(ctx: QueryContext, scope_name: str) -> dict[str, Any]:
    """Run the deterministic assessment and return the JSON payload."""
    return assess_scope(ctx, scope_name).to_dict()
