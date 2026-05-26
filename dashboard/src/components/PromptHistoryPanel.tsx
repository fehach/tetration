import { Clock, History, Trash2 } from "lucide-react";
import { useState } from "react";
import type { PromptHistoryEntry } from "../api/types";

interface Props {
  entries: PromptHistoryEntry[];
  loading: boolean;
  disabled: boolean;
  onSelect: (message: string) => void;
  onClear: () => Promise<void> | void;
}

function relative(timestamp: number): string {
  const seconds = Math.max(0, Math.floor((Date.now() / 1000) - timestamp));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export function PromptHistoryPanel({ entries, loading, disabled, onSelect, onClear }: Props) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-lg border border-surface-border/60 bg-surface-secondary/30">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted hover:text-white"
        >
          <History className="h-3.5 w-3.5" aria-hidden />
          Prompt history
          <span className="rounded-full bg-surface-card px-2 py-0.5 text-[10px] text-muted-dim">
            {entries.length}
          </span>
        </button>
        {entries.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            disabled={disabled}
            className="inline-flex items-center gap-1 text-[11px] text-muted hover:text-cisco-red disabled:opacity-50"
          >
            <Trash2 className="h-3 w-3" aria-hidden /> Clear
          </button>
        )}
      </header>
      {expanded && (
        <div className="border-t border-surface-border/40 px-2 py-2">
          {loading ? (
            <p className="px-2 py-3 text-xs text-muted">Loading…</p>
          ) : entries.length === 0 ? (
            <p className="px-2 py-3 text-xs text-muted">
              No prompts yet. Questions you send will appear here for quick reuse.
            </p>
          ) : (
            <ul className="max-h-[180px] space-y-1 overflow-y-auto">
              {entries.map((entry, idx) => (
                <li key={`${entry.timestamp}-${idx}`}>
                  <button
                    type="button"
                    onClick={() => onSelect(entry.message)}
                    disabled={disabled}
                    title={entry.message}
                    className="flex w-full items-center justify-between gap-3 rounded px-2 py-1.5 text-left text-xs text-muted transition hover:bg-surface-hover/40 hover:text-white disabled:opacity-50"
                  >
                    <span className="truncate">{entry.message}</span>
                    <span className="inline-flex shrink-0 items-center gap-1 text-[10px] text-muted-dim">
                      <Clock className="h-3 w-3" aria-hidden /> {relative(entry.timestamp)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
