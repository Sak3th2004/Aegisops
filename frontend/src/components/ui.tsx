import type { ReactNode } from "react";
import type { IncidentStatus, Severity } from "../types";

// Status → color mapping used across the header pill and the graph.
export const STATUS_STYLE: Record<IncidentStatus, { label: string; cls: string; dot: string }> = {
  DETECTED: { label: "Detected", cls: "text-signal-amber border-signal-amber/30 bg-signal-amber/10", dot: "bg-signal-amber" },
  TRIAGED: { label: "Triaged", cls: "text-signal-amber border-signal-amber/30 bg-signal-amber/10", dot: "bg-signal-amber" },
  DIAGNOSED: { label: "Diagnosed", cls: "text-signal-blue border-signal-blue/30 bg-signal-blue/10", dot: "bg-signal-blue" },
  CORRELATED: { label: "Correlated", cls: "text-signal-blue border-signal-blue/30 bg-signal-blue/10", dot: "bg-signal-blue" },
  AWAITING_APPROVAL: { label: "Awaiting Approval", cls: "text-signal-violet border-signal-violet/40 bg-signal-violet/10", dot: "bg-signal-violet" },
  REMEDIATING: { label: "Remediating", cls: "text-signal-blue border-signal-blue/30 bg-signal-blue/10", dot: "bg-signal-blue" },
  RESOLVED: { label: "Resolved", cls: "text-signal-green border-signal-green/30 bg-signal-green/10", dot: "bg-signal-green" },
  REJECTED: { label: "Rejected", cls: "text-signal-red border-signal-red/30 bg-signal-red/10", dot: "bg-signal-red" },
  FAILED: { label: "Failed", cls: "text-signal-red border-signal-red/30 bg-signal-red/10", dot: "bg-signal-red" },
};

const SEV_STYLE: Record<Severity, string> = {
  SEV1: "text-signal-red border-signal-red/40 bg-signal-red/10",
  SEV2: "text-signal-amber border-signal-amber/40 bg-signal-amber/10",
  SEV3: "text-signal-blue border-signal-blue/40 bg-signal-blue/10",
  SEV4: "text-slate-300 border-white/20 bg-white/5",
};

export function StatusPill({ status }: { status: IncidentStatus }) {
  const s = STATUS_STYLE[status];
  const pulsing = status === "AWAITING_APPROVAL" || status === "REMEDIATING";
  return (
    <span className={`chip ${s.cls}`} role="status" aria-label={`status ${s.label}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot} ${pulsing ? "animate-blink" : ""}`} />
      {s.label}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity)
    return <span className="chip border-white/10 bg-white/5 text-slate-400">SEV —</span>;
  return <span className={`chip font-semibold ${SEV_STYLE[severity]}`}>{severity}</span>;
}

export function RiskBadge({ risk }: { risk: string }) {
  const r = risk.toLowerCase();
  const cls =
    r === "high"
      ? "text-signal-red border-signal-red/40 bg-signal-red/10"
      : r === "medium"
      ? "text-signal-amber border-signal-amber/40 bg-signal-amber/10"
      : "text-signal-green border-signal-green/40 bg-signal-green/10";
  return <span className={`chip uppercase ${cls}`}>risk: {risk}</span>;
}

export function PanelTitle({
  icon,
  children,
  right,
}: {
  icon?: ReactNode;
  children: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="panel-header">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
        {icon}
        {children}
      </div>
      {right}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-h-[120px] flex-col items-center justify-center gap-2 p-6 text-center text-xs text-slate-500">
      {children}
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-signal-blue ${className}`}
      aria-hidden
    />
  );
}
