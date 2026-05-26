"""Pre-built query catalog. Each entry exposes a label and a callable."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from csw_agent.cache import TTLCache

if TYPE_CHECKING:
    from csw_agent.ai.claude import ClaudeRunner
    from csw_agent.client import CSWClient
    from csw_agent.config import Settings


@dataclass
class QueryContext:
    """Mutable shared state passed to every query function."""

    client: CSWClient
    settings: Settings
    claude: ClaudeRunner | None = None
    last_generated_csv: Path | None = None
    workspace_cache: TTLCache = field(init=False)

    def __post_init__(self) -> None:
        self.workspace_cache = TTLCache(self.settings.workspace_cache_ttl_seconds)


@dataclass(frozen=True)
class Query:
    """A single pre-built query entry exposed in the menu."""

    key: str
    label: str
    func: Callable[[QueryContext], None]


def build_registry() -> list[Query]:
    """Return the ordered list of queries shown in the local menu."""
    from csw_agent.queries import agents, csv_chat, enforcement, inventory, vulnerabilities, workspaces

    return [
        Query("1", "Agent summary (by platform & type)", agents.agent_summary),
        Query("2", "Workspace summary (analysis/enforcement)", workspaces.workspace_summary),
        Query("3", "Scope hierarchy", workspaces.scope_tree),
        Query("4", "Search workspace by name", workspaces.search_workspace),
        Query("5", "Search inventory (by hostname or IP)", inventory.search_inventory),
        Query("6", "List VRFs", inventory.list_vrfs),
        Query("7", "Service health check", inventory.service_health),
        Query("8", "Agents enforcement status (enabled/disabled)", enforcement.enforcement_status),
        Query("9", "Workspaces by scope (CSV)", workspaces.workspaces_by_scope),
        Query("10", "Agent version distribution", agents.agent_versions),
        Query("11", "Recently created/deleted/uninstalled agents (30 days)", agents.recent_agents),
        Query("12", "Vulnerability report (export to CSV)", vulnerabilities.vulnerability_report),
        Query(
            "13", "Agents without enforcement & not in enforcement workspace", enforcement.no_enf_no_workspace
        ),
        Query("14", "Agents with enforcement & in enforcement workspace (CSV)", enforcement.enf_in_workspace),
        Query(
            "15",
            "Agents without enforcement & in enforcement workspace (CSV)",
            enforcement.no_enf_in_enf_workspace,
        ),
        Query("16", "Ask Claude about last exported CSV", csv_chat.chat_about_last_csv),
    ]
