import { ChevronRight, MessageSquare, Settings, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";

const SHORTCUTS = [
  {
    to: "/queries",
    icon: Wrench,
    title: "Run queries",
    description:
      "Local report catalog: agents, workspaces, enforcement, vulnerabilities.",
    cta: "Open queries",
  },
  {
    to: "/chat",
    icon: MessageSquare,
    title: "Ask Claude",
    description:
      "Converse in natural language. Claude generates code, validates it, and shows the result.",
    cta: "Open chat",
  },
  {
    to: "/configuration",
    icon: Settings,
    title: "Configuration",
    description: "Connection status, active model, safe mode.",
    cta: "View configuration",
  },
];

export function HomePage() {
  const { data: health } = usePolling(api.health, 8000);

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-white">
              Welcome to the CSW Agent Dashboard
            </h2>
            <p className="mt-1 text-sm text-muted">
              Run local queries on your Cisco Secure Workload deployment or ask Claude to
              generate them for you.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 md:items-end">
            <span className="text-[11px] uppercase tracking-wider text-muted">Status</span>
            <span
              className={`text-sm font-medium ${
                health?.csw_connected ? "text-cisco-green" : "text-cisco-yellow"
              }`}
            >
              {health?.csw_connected
                ? "CSW connected"
                : health
                  ? "CSW not connected"
                  : "Checking…"}
            </span>
            <span className="text-xs text-muted-dim">{health?.endpoint ?? "—"}</span>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {SHORTCUTS.map(({ to, icon: Icon, title, description, cta }) => (
          <Link
            key={to}
            to={to}
            className="group rounded-lg border border-surface-border/60 bg-surface-card p-5 shadow-card transition hover:border-cisco-blue/60 hover:bg-surface-hover/30"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-cisco-blue/10">
                <Icon className="h-5 w-5 text-cisco-blue" aria-hidden />
              </div>
              <h3 className="text-base font-semibold text-white">{title}</h3>
            </div>
            <p className="mt-3 text-sm text-muted">{description}</p>
            <div className="mt-4 flex items-center gap-1 text-xs font-medium text-cisco-blue group-hover:underline">
              {cta}
              <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            </div>
          </Link>
        ))}
      </div>

      <Card title="How it works">
        <ol className="space-y-3 text-sm text-muted">
          <li>
            <strong className="text-white">Queries:</strong> run pre-built reports (no API
            knowledge needed). Some require an input like a workspace name or IP.
          </li>
          <li>
            <strong className="text-white">Chat with Claude:</strong> describe what you want in
            natural language. Claude generates the code, the sandbox validates it, and it only
            runs if safe.
          </li>
          <li>
            <strong className="text-white">CSV:</strong> reports can generate downloadable CSV
            files directly from the result.
          </li>
          <li>
            <strong className="text-white">Safe mode:</strong> blocks destructive operations
            (DELETE, modifications). Keep it enabled unless needed.
          </li>
        </ol>
      </Card>
    </div>
  );
}
