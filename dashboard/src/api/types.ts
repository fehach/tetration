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

export interface ComplianceScope {
  name: string;
  suggested: boolean;
}

export type PciStatus = "pass" | "warn" | "fail";

export interface PciCheck {
  title: string;
  status: PciStatus;
  detail: string;
}

export interface PciRequirement {
  id: string;
  title: string;
  status: PciStatus;
  points: number;
  max_points: number;
  checks: PciCheck[];
}

export interface PciAssessment {
  scope_name: string;
  generated_at: string;
  score: number;
  max_score: number;
  level: { label: string; tone: PciStatus };
  kpis: {
    workloads_total: number;
    workloads_with_agent: number;
    coverage_pct: number;
    critical_cves: number;
    cve_hosts: number;
    workspaces_total: number;
    workspaces_enforced: number;
  };
  requirements: PciRequirement[];
  tables: {
    workspaces: Record<string, unknown>[];
    critical_cves: Record<string, unknown>[];
    no_agent: Record<string, unknown>[];
  };
  evidence_file: string | null;
}

export interface ChatHistoryEntry {
  role: "user" | "assistant";
  content: string;
}

export interface PromptHistoryEntry {
  timestamp: number;
  message: string;
}
