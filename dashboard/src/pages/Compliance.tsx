import { Download, Info, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type {
  ComplianceScope,
  PciAssessment,
  PciRequirement,
  PciStatus,
  ResultTable as ResultTableType,
} from "../api/types";
import { Card } from "../components/Card";
import { ResultTable } from "../components/ResultTable";
import { StatusBadge } from "../components/StatusBadge";

const BADGE_STATE: Record<PciStatus, "ok" | "warn" | "error"> = {
  pass: "ok",
  warn: "warn",
  fail: "error",
};

const BADGE_LABEL: Record<PciStatus, string> = { pass: "Pass", warn: "Warn", fail: "Fail" };

const TONE_TEXT: Record<PciStatus, string> = {
  pass: "text-cisco-green",
  warn: "text-cisco-yellow",
  fail: "text-cisco-red",
};

const TONE_BG: Record<PciStatus, string> = {
  pass: "bg-cisco-green",
  warn: "bg-cisco-yellow",
  fail: "bg-cisco-red",
};

export function CompliancePage() {
  const [scopes, setScopes] = useState<ComplianceScope[] | null>(null);
  const [scope, setScope] = useState("");
  const [assessment, setAssessment] = useState<PciAssessment | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const list = await api.complianceScopes();
        setScopes(list);
        if (list.length > 0) setScope(list[0].name);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  const runAssessment = async () => {
    if (!scope) return;
    setRunning(true);
    setError(null);
    try {
      setAssessment(await api.complianceAssess(scope));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card title="PCI-DSS Compliance" subtitle="Readiness assessment of a CDE scope, built from live CSW evidence.">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-64 flex-col gap-1.5">
            <span className="text-xs uppercase tracking-wider text-muted">
              CDE scope (Cardholder Data Environment)
            </span>
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              disabled={!scopes || scopes.length === 0}
              className="rounded border border-surface-border bg-surface px-3 py-2 text-sm text-white"
            >
              {(scopes ?? []).map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                  {s.suggested ? " — suggested" : ""}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => void runAssessment()}
            disabled={running || !scope}
            className="inline-flex items-center gap-2 rounded bg-cisco-blue px-4 py-2 text-sm font-semibold text-white transition hover:brightness-90 disabled:opacity-50"
          >
            <Play className="h-4 w-4" aria-hidden />
            {running ? "Assessing…" : "Run assessment"}
          </button>
          {assessment?.evidence_file && (
            <a
              href={api.fileUrl(assessment.evidence_file)}
              className="inline-flex items-center gap-2 rounded border border-cisco-blue px-4 py-2 text-sm font-semibold text-cisco-blue transition hover:bg-cisco-blue/10"
            >
              <Download className="h-4 w-4" aria-hidden />
              Export evidence CSV
            </a>
          )}
        </div>
        {scopes !== null && scopes.length === 0 && (
          <p className="mt-3 text-sm text-muted">No scopes found in this CSW deployment.</p>
        )}
      </Card>

      <div className="flex items-start gap-2.5 rounded border-l-4 border-cisco-blue bg-surface px-4 py-3 text-sm text-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-cisco-blue" aria-hidden />
        <p>
          <span className="font-semibold text-white">
            Compliance readiness view — not an official assessment.
          </span>{" "}
          Checks map live Cisco Secure Workload evidence to a verifiable subset of PCI-DSS v4.0.1
          (Req 1, 6, 7, 10, 11). Formal validation requires a Qualified Security Assessor (QSA).
        </p>
      </div>

      {error && (
        <Card title="Error">
          <p className="text-sm text-cisco-red">{error}</p>
        </Card>
      )}

      {!assessment && !error && (
        <Card title="No assessment yet">
          <p className="text-sm text-muted">
            Pick the scope that represents your Cardholder Data Environment and run the assessment.
            Scopes whose name contains “PCI” or “CDE” are suggested automatically.
          </p>
        </Card>
      )}

      {assessment && <AssessmentView assessment={assessment} />}
    </div>
  );
}

function AssessmentView({ assessment }: { assessment: PciAssessment }) {
  const { kpis } = assessment;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <ScoreGauge assessment={assessment} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Kpi
            label="CDE workloads"
            value={kpis.workloads_total.toLocaleString()}
            sub="inventory items in scope"
            tone="pass"
          />
          <Kpi
            label="Agent coverage"
            value={`${kpis.coverage_pct}%`}
            sub={`${kpis.workloads_with_agent} of ${kpis.workloads_total} workloads · target ≥ 95%`}
            tone={kpis.coverage_pct >= 95 ? "pass" : kpis.coverage_pct >= 85 ? "warn" : "fail"}
          />
          <Kpi
            label="Critical CVEs"
            value={kpis.critical_cves.toLocaleString()}
            sub={`CVSS ≥ 7.0 · on ${kpis.cve_hosts} hosts`}
            tone={kpis.critical_cves === 0 ? "pass" : "fail"}
          />
          <Kpi
            label="Enforced workspaces"
            value={`${kpis.workspaces_enforced}/${kpis.workspaces_total}`}
            sub="enforcement enabled"
            tone={
              kpis.workspaces_total > 0 && kpis.workspaces_enforced === kpis.workspaces_total
                ? "pass"
                : "warn"
            }
          />
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-base font-semibold tracking-tight">
          Requirements — evidence-backed checks
        </h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {assessment.requirements.map((req) => (
            <RequirementCard key={req.id} requirement={req} />
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <ResultTable table={workspacesTable(assessment)} />
        </Card>
        <Card>
          <ResultTable table={cvesTable(assessment)} />
        </Card>
      </div>
      <Card>
        <ResultTable table={noAgentTable(assessment)} />
      </Card>

      <p className="text-xs text-muted-dim">
        Assessment generated {assessment.generated_at} · deterministic engine ·{" "}
        {assessment.evidence_file
          ? `evidence file ${assessment.evidence_file}`
          : "no evidence rows to export"}
      </p>
    </div>
  );
}

function ScoreGauge({ assessment }: { assessment: PciAssessment }) {
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const tone = assessment.level.tone;
  return (
    <Card className="flex flex-col items-center gap-3">
      <span className="self-start text-xs uppercase tracking-wider text-muted">
        Overall readiness score
      </span>
      <div className="relative h-[150px] w-[150px]">
        <svg width="150" height="150" viewBox="0 0 150 150" className="-rotate-90">
          <circle
            cx="75"
            cy="75"
            r={radius}
            fill="none"
            strokeWidth="11"
            className="stroke-surface-border"
          />
          <circle
            cx="75"
            cy="75"
            r={radius}
            fill="none"
            strokeWidth="11"
            strokeLinecap="round"
            stroke="currentColor"
            className={TONE_TEXT[tone]}
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - assessment.score / assessment.max_score)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="tabular text-3xl font-semibold">{assessment.score}</span>
          <span className="text-[11px] text-muted-dim">/ {assessment.max_score} pts</span>
        </div>
      </div>
      <StatusBadge state={BADGE_STATE[tone]} label={assessment.level.label} />
      <span className="text-center text-xs text-muted-dim">{assessment.scope_name}</span>
    </Card>
  );
}

function Kpi({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub: string;
  tone: PciStatus;
}) {
  return (
    <Card className="flex flex-col justify-center gap-1">
      <span className="text-xs uppercase tracking-wider text-muted">{label}</span>
      <span className="tabular text-3xl font-semibold">{value}</span>
      <span className="flex items-center gap-2 text-xs text-muted-dim">
        <span className={`h-2 w-2 shrink-0 rounded-full ${TONE_BG[tone]}`} aria-hidden />
        {sub}
      </span>
    </Card>
  );
}

function RequirementCard({ requirement }: { requirement: PciRequirement }) {
  const pct = requirement.max_points
    ? Math.round((100 * requirement.points) / requirement.max_points)
    : 0;
  return (
    <Card>
      <div className="mb-1 flex items-start justify-between gap-2">
        <div>
          <span className="text-xs uppercase tracking-wider text-muted">{requirement.id}</span>
          <h3 className="text-sm font-semibold text-white">{requirement.title}</h3>
        </div>
        <StatusBadge state={BADGE_STATE[requirement.status]} label={BADGE_LABEL[requirement.status]} />
      </div>
      <p className="tabular mb-2 text-xs text-muted">
        {requirement.points} / {requirement.max_points} pts
      </p>
      <div className="mb-3.5 h-1.5 overflow-hidden rounded bg-surface">
        <div
          className={`h-full rounded ${TONE_BG[requirement.status]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <ul className="space-y-2 text-xs text-muted">
        {requirement.checks.map((check) => (
          <li key={check.title} className="flex items-baseline gap-2">
            <span
              className={`relative top-[-1px] h-2 w-2 shrink-0 rounded-full ${TONE_BG[check.status]}`}
              aria-hidden
            />
            <span>
              {check.title} — <span className="font-semibold text-white">{check.detail}</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function workspacesTable(assessment: PciAssessment): ResultTableType {
  return {
    title: "CDE workspaces — segmentation posture (Req 1 · 11.4.4)",
    columns: [
      { key: "name", label: "Workspace" },
      { key: "enforcement_enabled", label: "Enforce" },
      { key: "catch_all", label: "Catch-all" },
      { key: "policy_count", label: "Policies", numeric: true },
      { key: "analyzed_version", label: "Analyzed", numeric: true },
      { key: "status_label", label: "Status" },
    ],
    rows: assessment.tables.workspaces.map((row) => ({
      ...row,
      status_label: BADGE_LABEL[(row.status as PciStatus) ?? "fail"],
    })),
  };
}

function cvesTable(assessment: PciAssessment): ResultTableType {
  return {
    title: "Critical CVEs on CDE workloads (Req 6 · 11.3)",
    columns: [
      { key: "host", label: "Host" },
      { key: "cve_id", label: "CVE" },
      { key: "severity", label: "Severity" },
      { key: "cvss", label: "CVSS", numeric: true },
      { key: "package", label: "Package" },
      { key: "fixed_version", label: "Fixed in" },
    ],
    rows: assessment.tables.critical_cves,
  };
}

function noAgentTable(assessment: PciAssessment): ResultTableType {
  return {
    title: "Workloads without agent (Req 10)",
    columns: [
      { key: "host", label: "Host" },
      { key: "ip", label: "IP address" },
      { key: "os", label: "OS" },
      { key: "vrf", label: "VRF" },
    ],
    rows: assessment.tables.no_agent,
  };
}
