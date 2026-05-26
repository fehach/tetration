import { useMemo, useState } from "react";
import type { ResultTable as ResultTableType } from "../api/types";

interface Props {
  table: ResultTableType;
}

export function ResultTable({ table }: Props) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = useMemo(() => {
    if (!sortKey) return table.rows;
    const copy = [...table.rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [table.rows, sortKey, sortDir]);

  const onHeaderClick = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-white">{table.title}</h3>
      <div className="overflow-x-auto rounded border border-surface-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-secondary/60">
              {table.columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => onHeaderClick(col.key)}
                  className={`cursor-pointer select-none px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted hover:text-white ${
                    col.numeric ? "text-right" : ""
                  }`}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1 text-cisco-blue">
                      {sortDir === "asc" ? "↑" : "↓"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={table.columns.length}
                  className="px-3 py-6 text-center text-muted"
                >
                  Sin resultados.
                </td>
              </tr>
            ) : (
              sorted.map((row, i) => (
                <tr
                  key={i}
                  className="border-t border-surface-border/40 hover:bg-surface-hover/30"
                >
                  {table.columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-3 py-2 ${col.numeric ? "tabular text-right" : ""}`}
                    >
                      {formatCell(row[col.key])}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value);
}
