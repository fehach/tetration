export interface Health {
  version: string;
  csw_connected: boolean;
  endpoint: string;
  model: string;
  claudegate_url: string;
  safe_mode: boolean;
}

export interface AppConfig {
  api_endpoint: string;
  credentials_file: string;
  claude_model: string;
  claudegate_url: string;
  safe_mode: boolean;
  verify_tls: boolean;
  log_level: string;
}

export interface QueryInput {
  name: string;
  label: string;
  placeholder: string;
  required: boolean;
}

export interface WebQuery {
  key: string;
  label: string;
  description: string;
  category: string;
  result_kind: "structured" | "stdout";
  needs_csw: boolean;
  inputs: QueryInput[];
}

export interface ResultColumn {
  key: string;
  label: string;
  numeric?: boolean;
}

export interface ResultTable {
  title: string;
  columns: ResultColumn[];
  rows: Record<string, unknown>[];
}

export interface StructuredResult {
  summary?: Record<string, unknown>;
  tables?: ResultTable[];
  error?: string;
}

export interface StdoutResult {
  stdout: string;
  files: string[];
  success: boolean;
  error?: string | null;
}

export type QueryResult =
  | { kind: "structured"; data: StructuredResult; started_at: string }
  | { kind: "stdout"; data: StdoutResult; started_at: string };

export type ChatEvent =
  | { type: "thinking" }
  | { type: "text"; chunk: string }
  | { type: "code"; code: string }
  | {
      type: "sandbox";
      is_safe: boolean;
      has_destructive_intent: boolean;
      violations: string[];
    }
  | { type: "output"; stdout: string; error: string | null; iso_time: string }
  | { type: "usage"; tokens_in: number; tokens_out: number }
  | { type: "warning"; message: string }
  | { type: "error"; message: string }
  | { type: "done" };

export interface ChatHistoryEntry {
  role: "user" | "assistant";
  content: string;
}

export interface PromptHistoryEntry {
  timestamp: number;
  message: string;
}
