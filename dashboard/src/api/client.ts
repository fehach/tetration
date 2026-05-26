import type {
  AppConfig,
  ChatEvent,
  ChatHistoryEntry,
  Health,
  PromptHistoryEntry,
  QueryResult,
  WebQuery,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text.slice(0, 240)}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/health"),
  config: () => request<AppConfig>("/config"),
  patchConfig: (body: { safe_mode?: boolean }) =>
    request<{ safe_mode: boolean }>("/config", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  queries: () => request<WebQuery[]>("/queries"),
  runQuery: (key: string, inputs: Record<string, string>) =>
    request<QueryResult>(`/queries/${key}/run`, {
      method: "POST",
      body: JSON.stringify({ inputs }),
    }),
  fileUrl: (filename: string) => `${BASE}/files/${encodeURIComponent(filename)}`,
  chatHistory: () => request<ChatHistoryEntry[]>("/chat/history"),
  chatReset: () => request<{ ok: boolean }>("/chat/reset", { method: "POST" }),
  promptHistory: (limit = 50) =>
    request<PromptHistoryEntry[]>(`/chat/prompts?limit=${limit}`),
  clearPromptHistory: () =>
    request<{ ok: boolean }>("/chat/prompts", { method: "DELETE" }),
};

/**
 * Open a streaming chat connection. The caller receives parsed events one at a
 * time and an optional ``onError`` callback for transport-level failures.
 */
export async function streamChat(
  message: string,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    throw new Error(`Chat failed: ${resp.status} ${text.slice(0, 200)}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        onEvent(JSON.parse(line.slice(6)) as ChatEvent);
      } catch {
        /* ignore malformed frames */
      }
    }
  }
}
