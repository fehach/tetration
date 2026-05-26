import { ServerCog } from "lucide-react";
import { api } from "../api/client";
import { usePolling } from "../hooks/usePolling";
import { StatusBadge } from "./StatusBadge";

export function Header() {
  const { data: health } = usePolling(api.health, 8000);
  const cswState = health ? (health.csw_connected ? "ok" : "warn") : "info";
  const cswLabel = health
    ? health.csw_connected
      ? "CSW connected"
      : "CSW disconnected"
    : "Connecting…";

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-surface-border bg-surface-sidebar/80 px-6 backdrop-blur">
      <div className="flex items-center gap-4">
        <ServerCog className="h-5 w-5 text-cisco-blue" aria-hidden />
        <div>
          <h1 className="text-sm font-semibold tracking-tight">CSW Agent</h1>
          <p className="text-[11px] text-muted">
            {health?.endpoint ?? "—"} · {health?.model ?? "—"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <StatusBadge state={cswState} label={cswLabel} />
        <StatusBadge
          state={health?.safe_mode ? "ok" : "warn"}
          label={health?.safe_mode ? "Safe mode" : "Safe mode OFF"}
        />
      </div>
    </header>
  );
}
