import { Home, MessageSquare, Settings, Sparkles, Wrench } from "lucide-react";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Inicio", icon: Home },
  { to: "/queries", label: "Consultas", icon: Wrench },
  { to: "/chat", label: "Chat con Claude", icon: MessageSquare },
  { to: "/configuration", label: "Configuración", icon: Settings },
];

// Watermark shown at the bottom of the sidebar. Edit the constants below
// to personalize the author name or remove the watermark.
const AUTHOR_NAME = "fehach";
const PRODUCT_YEAR = new Date().getFullYear();

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-surface-border bg-surface-sidebar lg:flex">
      <div className="px-5 py-5">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded bg-cisco-blue/15 flex items-center justify-center">
            <span className="text-cisco-blue text-sm font-bold">CSW</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-white">CSW Agent</p>
            <p className="text-[11px] text-muted">Asistente operacional</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 px-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition ${
                isActive
                  ? "bg-surface-selected text-white"
                  : "text-muted hover:bg-surface-hover hover:text-white"
              }`
            }
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <footer className="border-t border-surface-border px-5 py-4">
        <div className="flex items-center gap-1.5 text-[11px] text-muted-dim">
          <Sparkles className="h-3 w-3 text-cisco-blue" aria-hidden />
          <span>
            Hecho por <span className="text-white">{AUTHOR_NAME}</span> con asistencia de IA
          </span>
        </div>
        <p className="mt-1 text-[10px] text-muted-dim">© {PRODUCT_YEAR} · uso interno</p>
      </footer>
    </aside>
  );
}
