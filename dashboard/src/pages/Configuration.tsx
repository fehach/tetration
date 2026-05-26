import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AppConfig } from "../api/types";
import { Card } from "../components/Card";
import { Toggle } from "../components/Toggle";

export function ConfigurationPage() {
  const [data, setData] = useState<AppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void load();
  }, []);

  const load = async () => {
    try {
      setData(await api.config());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const setSafeMode = async (next: boolean) => {
    if (!data) return;
    setSaving(true);
    setError(null);
    try {
      await api.patchConfig({ safe_mode: next });
      setData({ ...data, safe_mode: next });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  if (error) {
    return (
      <Card title="Error">
        <p className="text-sm text-cisco-red">{error}</p>
      </Card>
    );
  }
  if (!data) {
    return (
      <Card title="Cargando…">
        <p className="text-sm text-muted">Recuperando configuración del agente.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <Card title="Modo de operación">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-white">Modo seguro</p>
            <p className="mt-1 text-xs text-muted">
              Cuando está activado, las consultas o el código generado por Claude que intenten
              borrar, modificar o crear datos en CSW son bloqueadas por el sandbox. Mantenlo
              activado salvo que un administrador necesite operaciones destructivas.
            </p>
          </div>
          <Toggle checked={data.safe_mode} onChange={setSafeMode} disabled={saving} />
        </div>
      </Card>

      <Card title="Conexión" subtitle="Solo lectura — se configura por variables de entorno o flags de la CLI.">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-3 text-sm md:grid-cols-2">
          <Field label="CSW Endpoint" value={data.api_endpoint} mono />
          <Field label="Credenciales" value={data.credentials_file} mono />
          <Field
            label="Verificación TLS"
            value={data.verify_tls ? "Activa" : "Desactivada"}
            tone={data.verify_tls ? "ok" : "warn"}
          />
          <Field label="Nivel de logs" value={data.log_level} />
        </dl>
      </Card>

      <Card title="Claude AI" subtitle="Modelo y proxy ClaudeGate utilizados para el chat.">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-3 text-sm md:grid-cols-2">
          <Field label="Modelo" value={data.claude_model} mono />
          <Field label="ClaudeGate URL" value={data.claudegate_url} mono />
        </dl>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  mono,
  tone,
}: {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "ok" | "warn";
}) {
  const color =
    tone === "ok" ? "text-cisco-green" : tone === "warn" ? "text-cisco-yellow" : "text-white";
  return (
    <div className="flex items-start justify-between gap-4 border-b border-surface-border/40 pb-2">
      <dt className="text-xs uppercase tracking-wider text-muted">{label}</dt>
      <dd className={`text-right text-sm ${mono ? "font-mono text-xs" : ""} ${color}`}>
        {value}
      </dd>
    </div>
  );
}
