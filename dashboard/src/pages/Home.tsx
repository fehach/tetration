import { ChevronRight, MessageSquare, Settings, Wrench } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";

const SHORTCUTS = [
  {
    to: "/queries",
    icon: Wrench,
    title: "Ejecutar consultas",
    description:
      "Catálogo de informes locales: agentes, workspaces, enforcement, vulnerabilidades.",
    cta: "Abrir consultas",
  },
  {
    to: "/chat",
    icon: MessageSquare,
    title: "Preguntar a Claude",
    description:
      "Conversa en lenguaje natural. Claude genera código, lo valida y muestra el resultado.",
    cta: "Abrir chat",
  },
  {
    to: "/configuration",
    icon: Settings,
    title: "Configuración",
    description: "Estado de la conexión, modelo en uso, modo seguro.",
    cta: "Ver configuración",
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
              Bienvenido al panel del CSW Agent
            </h2>
            <p className="mt-1 text-sm text-muted">
              Ejecuta consultas locales sobre tu despliegue de Cisco Secure Workload o pide
              a Claude que las genere por ti.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1 md:items-end">
            <span className="text-[11px] uppercase tracking-wider text-muted">Estado</span>
            <span
              className={`text-sm font-medium ${
                health?.csw_connected ? "text-cisco-green" : "text-cisco-yellow"
              }`}
            >
              {health?.csw_connected
                ? "CSW conectado"
                : health
                  ? "Sin conexión a CSW"
                  : "Comprobando…"}
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

      <Card title="Cómo funciona">
        <ol className="space-y-3 text-sm text-muted">
          <li>
            <strong className="text-white">Consultas:</strong> ejecuta informes pre-construidos
            (no requieren conocer la API). Algunas piden un dato como nombre de workspace o IP.
          </li>
          <li>
            <strong className="text-white">Chat con Claude:</strong> describe lo que quieres en
            español o inglés. Claude genera el código necesario, el sandbox lo valida, y se
            ejecuta solo si es seguro.
          </li>
          <li>
            <strong className="text-white">CSV:</strong> los informes pueden generar archivos
            CSV descargables directamente desde el resultado.
          </li>
          <li>
            <strong className="text-white">Modo seguro:</strong> bloquea operaciones
            destructivas (DELETE, modificaciones). Mantenlo siempre activado salvo necesidad.
          </li>
        </ol>
      </Card>
    </div>
  );
}
