import { AlertTriangle, RefreshCw, Send, Shield, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, streamChat } from "../api/client";
import type { ChatEvent, PromptHistoryEntry } from "../api/types";
import { Card } from "../components/Card";
import { PromptHistoryPanel } from "../components/PromptHistoryPanel";

interface CodeBlock {
  code: string;
  sandbox?: { is_safe: boolean; has_destructive_intent: boolean; violations: string[] };
  output?: { stdout: string; error: string | null };
}

interface AssistantTurn {
  role: "assistant";
  text: string;
  code?: CodeBlock;
  warning?: string;
  errorMessage?: string;
  usage?: { tokens_in: number; tokens_out: number };
  thinking: boolean;
}

interface UserTurn {
  role: "user";
  text: string;
}

type Turn = AssistantTurn | UserTurn;

const SUGGESTIONS = [
  "How many agents are running on Linux?",
  "List workspaces with enforcement enabled.",
  "Show flows from 10.27.204.40 in the last hour.",
];

export function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [promptHistory, setPromptHistory] = useState<PromptHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshHistory = useCallback(async () => {
    try {
      setPromptHistory(await api.promptHistory());
    } catch {
      /* non-fatal: just leave previous history */
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [turns]);

  const clearHistory = async () => {
    await api.clearPromptHistory();
    await refreshHistory();
  };

  const send = async (message: string) => {
    if (!message.trim() || busy) return;
    setBusy(true);
    setInput("");
    setTurns((prev) => [
      ...prev,
      { role: "user", text: message },
      { role: "assistant", text: "", thinking: true },
    ]);

    const updateAssistant = (patch: (prev: AssistantTurn) => AssistantTurn) => {
      setTurns((prev) => {
        const idx = prev.length - 1;
        const last = prev[idx];
        if (last.role !== "assistant") return prev;
        return [...prev.slice(0, idx), patch(last)];
      });
    };

    try {
      await streamChat(message, (event) => handleEvent(event, updateAssistant));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : String(err);
      updateAssistant((prev) => ({ ...prev, errorMessage, thinking: false }));
    } finally {
      setBusy(false);
      void refreshHistory();
    }
  };

  const reset = async () => {
    await api.chatReset();
    setTurns([]);
  };

  return (
    <Card
      title="Chat with Claude"
      subtitle="Ask anything about your CSW deployment. Claude will generate the code and show you the result."
      actions={
        <button
          type="button"
          onClick={reset}
          disabled={busy || turns.length === 0}
          className="inline-flex items-center gap-1.5 rounded-md border border-surface-border px-3 py-1 text-xs text-muted hover:text-white disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Reset
        </button>
      }
    >
      <div
        ref={scrollRef}
        className="max-h-[60vh] space-y-4 overflow-y-auto pr-1"
        aria-live="polite"
      >
        {turns.length === 0 ? (
          <EmptyChat onPick={(s) => send(s)} disabled={busy} />
        ) : (
          turns.map((turn, idx) =>
            turn.role === "user" ? (
              <UserBubble key={idx} text={turn.text} />
            ) : (
              <AssistantBubble key={idx} turn={turn} />
            ),
          )
        )}
      </div>

      <div className="mt-4">
        <PromptHistoryPanel
          entries={promptHistory}
          loading={historyLoading}
          disabled={busy}
          onSelect={(message) => setInput(message)}
          onClear={clearHistory}
        />
      </div>

      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          placeholder="Type your question. Enter to send, Shift+Enter for a new line."
          rows={2}
          className="flex-1 resize-none rounded-md border border-surface-border bg-surface-secondary/40 p-3 text-sm text-white placeholder:text-muted-dim focus:border-cisco-blue focus:outline-none"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className={`inline-flex items-center gap-2 rounded-md px-4 py-3 text-sm font-medium transition ${
            busy || !input.trim()
              ? "cursor-not-allowed bg-surface-border text-muted"
              : "bg-cisco-blue text-white hover:brightness-110"
          }`}
        >
          <Send className="h-4 w-4" aria-hidden />
          Send
        </button>
      </form>
    </Card>
  );
}

function handleEvent(
  event: ChatEvent,
  update: (patch: (prev: AssistantTurn) => AssistantTurn) => void,
): void {
  switch (event.type) {
    case "thinking":
      update((prev) => ({ ...prev, thinking: true }));
      return;
    case "text":
      update((prev) => ({ ...prev, text: prev.text + event.chunk, thinking: true }));
      return;
    case "code":
      update((prev) => ({ ...prev, code: { code: event.code }, thinking: true }));
      return;
    case "sandbox":
      update((prev) => ({
        ...prev,
        code: prev.code
          ? {
              ...prev.code,
              sandbox: {
                is_safe: event.is_safe,
                has_destructive_intent: event.has_destructive_intent,
                violations: event.violations,
              },
            }
          : prev.code,
      }));
      return;
    case "output":
      update((prev) => ({
        ...prev,
        code: prev.code ? { ...prev.code, output: { stdout: event.stdout, error: event.error } } : prev.code,
      }));
      return;
    case "usage":
      update((prev) => ({
        ...prev,
        usage: { tokens_in: event.tokens_in, tokens_out: event.tokens_out },
      }));
      return;
    case "warning":
      update((prev) => ({ ...prev, warning: event.message }));
      return;
    case "error":
      update((prev) => ({ ...prev, errorMessage: event.message, thinking: false }));
      return;
    case "done":
      update((prev) => ({ ...prev, thinking: false }));
      return;
  }
}

function EmptyChat({
  onPick,
  disabled,
}: {
  onPick: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="rounded-lg border border-dashed border-surface-border/60 bg-surface-secondary/20 p-6 text-sm text-muted">
      <p>
        Ask anything about your deployment. Some ideas to get you started:
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onPick(s)}
            disabled={disabled}
            className="rounded-full border border-surface-border bg-surface-card px-3 py-1.5 text-xs text-white transition hover:border-cisco-blue hover:text-cisco-blue disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-lg bg-cisco-blue/15 px-4 py-2 text-sm text-white">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ turn }: { turn: AssistantTurn }) {
  return (
    <div className="space-y-2">
      <div className="rounded-lg border border-surface-border/60 bg-surface-card px-4 py-3 text-sm text-white">
        {turn.text ? (
          <p className="whitespace-pre-wrap">{turn.text}</p>
        ) : turn.thinking ? (
          <p className="text-muted">Thinking…</p>
        ) : (
          <p className="text-muted">(no text)</p>
        )}
        {turn.warning && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-cisco-yellow">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> {turn.warning}
          </p>
        )}
        {turn.errorMessage && (
          <p className="mt-2 inline-flex items-center gap-1.5 text-xs text-cisco-red">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> {turn.errorMessage}
          </p>
        )}
      </div>
      {turn.code && <CodePanel block={turn.code} />}
      {turn.usage && (
        <p className="text-right text-[10px] uppercase tracking-wider text-muted-dim">
          tokens · in {turn.usage.tokens_in} · out {turn.usage.tokens_out}
        </p>
      )}
    </div>
  );
}

function CodePanel({ block }: { block: CodeBlock }) {
  const sandboxOk = block.sandbox?.is_safe ?? true;
  return (
    <div className="rounded-lg border border-surface-border/60 bg-surface-secondary/40">
      <div className="flex items-center justify-between border-b border-surface-border/50 px-3 py-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted">
          Generated code
        </span>
        {block.sandbox &&
          (sandboxOk ? (
            <span className="inline-flex items-center gap-1.5 text-[11px] text-cisco-green">
              <Shield className="h-3 w-3" aria-hidden /> Sandbox: passed
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-[11px] text-cisco-red">
              <ShieldAlert className="h-3 w-3" aria-hidden /> Sandbox: blocked
            </span>
          ))}
      </div>
      <pre className="max-h-[280px] overflow-auto px-3 py-2 font-mono text-[11px] leading-snug text-white">
        {block.code}
      </pre>
      {block.sandbox && !sandboxOk && (
        <div className="border-t border-surface-border/50 px-3 py-2 text-[11px] text-cisco-red">
          Reason: {block.sandbox.violations.join("; ") || "—"}
        </div>
      )}
      {block.output && (
        <div className="border-t border-surface-border/50">
          <div className="px-3 py-2 text-[11px] uppercase tracking-wider text-muted">
            Output
          </div>
          {block.output.error && (
            <p className="px-3 pb-2 text-xs text-cisco-red">{block.output.error}</p>
          )}
          <pre className="max-h-[320px] overflow-auto px-3 pb-3 font-mono text-[11px] leading-snug text-white">
            {block.output.stdout || "(no output)"}
          </pre>
        </div>
      )}
    </div>
  );
}
