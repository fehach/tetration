import { ChevronDown, ChevronUp, Download, Loader2, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  QueryResult,
  StdoutResult,
  StructuredResult,
  WebQuery,
} from "../api/types";
import { Card } from "../components/Card";
import { ResultTable } from "../components/ResultTable";

interface QueryState {
  inputs: Record<string, string>;
  loading: boolean;
  result: QueryResult | null;
  error: string | null;
  expanded: boolean;
}

const initialState = (): QueryState => ({
  inputs: {},
  loading: false,
  result: null,
  error: null,
  expanded: true,
});

export function QueriesPage() {
  const [queries, setQueries] = useState<WebQuery[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<Record<string, QueryState>>({});

  useEffect(() => {
    api
      .queries()
      .then((data) => {
        setQueries(data);
        setState(Object.fromEntries(data.map((q) => [q.key, initialState()])));
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const grouped = useMemo(() => {
    if (!queries) return [];
    const map = new Map<string, WebQuery[]>();
    for (const q of queries) {
      if (!map.has(q.category)) map.set(q.category, []);
      map.get(q.category)!.push(q);
    }
    return Array.from(map.entries());
  }, [queries]);

  const update = (key: string, patch: Partial<QueryState>) =>
    setState((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const setInput = (key: string, name: string, value: string) =>
    setState((prev) => ({
      ...prev,
      [key]: { ...prev[key], inputs: { ...prev[key].inputs, [name]: value } },
    }));

  const run = async (query: WebQuery) => {
    update(query.key, { loading: true, error: null, result: null, expanded: true });
    try {
      const result = await api.runQuery(query.key, state[query.key]?.inputs ?? {});
      update(query.key, { loading: false, result });
    } catch (err) {
      update(query.key, {
        loading: false,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  };

  if (error) {
    return (
      <Card title="Error">
        <p className="text-sm text-cisco-red">{error}</p>
      </Card>
    );
  }
  if (!queries) {
    return (
      <Card title="Cargando consultas…">
        <Loader2 className="h-5 w-5 animate-spin text-cisco-blue" aria-hidden />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {grouped.map(([category, items]) => (
        <section key={category} className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            {category}
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {items.map((query) => {
              const queryState = state[query.key] ?? initialState();
              const canRun =
                !queryState.loading &&
                query.inputs.every(
                  (i) => !i.required || (queryState.inputs[i.name]?.trim() ?? "") !== "",
                );
              return (
                <article
                  key={query.key}
                  className="flex flex-col rounded-lg border border-surface-border/60 bg-surface-card p-5 shadow-card"
                >
                  <header>
                    <h3 className="text-sm font-semibold text-white">{query.label}</h3>
                    <p className="mt-1 text-xs text-muted">{query.description}</p>
                  </header>

                  {query.inputs.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {query.inputs.map((input) => (
                        <label key={input.name} className="block text-xs">
                          <span className="text-muted">{input.label}</span>
                          <input
                            type="text"
                            value={queryState.inputs[input.name] ?? ""}
                            onChange={(e) => setInput(query.key, input.name, e.target.value)}
                            placeholder={input.placeholder}
                            className="mt-1 w-full rounded border border-surface-border bg-surface-secondary/40 px-3 py-1.5 text-sm text-white placeholder:text-muted-dim focus:border-cisco-blue focus:outline-none"
                          />
                        </label>
                      ))}
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => run(query)}
                      disabled={!canRun}
                      className={`inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                        canRun
                          ? "bg-cisco-blue text-white hover:brightness-110"
                          : "cursor-not-allowed bg-surface-border text-muted"
                      }`}
                    >
                      {queryState.loading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                      ) : (
                        <Play className="h-3.5 w-3.5" aria-hidden />
                      )}
                      {queryState.loading ? "Ejecutando…" : "Ejecutar"}
                    </button>
                    {queryState.result && (
                      <button
                        type="button"
                        onClick={() =>
                          update(query.key, { expanded: !queryState.expanded })
                        }
                        className="inline-flex items-center gap-1 text-xs text-muted hover:text-white"
                      >
                        {queryState.expanded ? (
                          <>
                            <ChevronUp className="h-3.5 w-3.5" aria-hidden /> Ocultar
                          </>
                        ) : (
                          <>
                            <ChevronDown className="h-3.5 w-3.5" aria-hidden /> Mostrar
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {queryState.error && (
                    <p className="mt-3 rounded-md border-l-4 border-cisco-red bg-surface-secondary/40 p-3 text-xs text-cisco-red">
                      {queryState.error}
                    </p>
                  )}
                  {queryState.result && queryState.expanded && (
                    <div className="mt-4 border-t border-surface-border/40 pt-4">
                      <ResultPanel result={queryState.result} />
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function ResultPanel({ result }: { result: QueryResult }) {
  if (result.kind === "structured") return <StructuredResultView data={result.data} />;
  return <StdoutResultView data={result.data} />;
}

function StructuredResultView({ data }: { data: StructuredResult }) {
  if (data.error) {
    return (
      <div className="rounded-md border-l-4 border-cisco-red bg-surface-secondary/40 p-3 text-xs text-cisco-red">
        {data.error}
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {data.summary && (
        <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
          {Object.entries(data.summary).map(([k, v]) => (
            <div
              key={k}
              className="rounded border border-surface-border/60 bg-surface-secondary/30 p-2"
            >
              <dt className="text-[11px] uppercase tracking-wider text-muted">
                {humanize(k)}
              </dt>
              <dd className="mt-1 text-base font-semibold tabular text-white">
                {formatSummaryValue(v)}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {data.tables?.map((table) => <ResultTable key={table.title} table={table} />)}
    </div>
  );
}

function StdoutResultView({ data }: { data: StdoutResult }) {
  return (
    <div className="space-y-3">
      {data.error && (
        <div className="rounded-md border-l-4 border-cisco-red bg-surface-secondary/40 p-3 text-xs text-cisco-red">
          {data.error}
        </div>
      )}
      <pre className="max-h-[480px] overflow-auto rounded-md border border-surface-border bg-surface-background/80 p-3 font-mono text-[11px] leading-snug text-white">
        {data.stdout || "(sin salida)"}
      </pre>
      {data.files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {data.files.map((filename) => (
            <a
              key={filename}
              href={api.fileUrl(filename)}
              download={filename}
              className="inline-flex items-center gap-1.5 rounded-md border border-cisco-blue/60 bg-cisco-blue/10 px-3 py-1 text-xs text-cisco-blue hover:bg-cisco-blue/20"
            >
              <Download className="h-3.5 w-3.5" aria-hidden />
              {filename}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function humanize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatSummaryValue(value: unknown): string {
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value ?? "—");
}
