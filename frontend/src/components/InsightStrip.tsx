import { motion } from "framer-motion";
import {
  Brain,
  GitCommitHorizontal,
  MessageSquareText,
  ShieldCheck,
  Target,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import type { WarRoomState } from "../types";

function Card({
  icon: Icon,
  label,
  accent,
  children,
}: {
  icon: LucideIcon;
  label: string;
  accent: string;
  children: ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="panel flex flex-col gap-1.5 p-3.5"
    >
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        <Icon size={12} style={{ color: accent }} />
        {label}
      </div>
      <div className="text-[13px] text-slate-200">{children}</div>
    </motion.div>
  );
}

const dash = <span className="text-slate-600">—</span>;

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? "#3ddc97" : pct >= 50 ? "#ffb020" : "#ff5c5c";
  return (
    <div className="mt-1 flex items-center gap-2">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6 }}
        />
      </div>
      <span className="font-mono text-[11px]" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

export default function InsightStrip({ state }: { state: WarRoomState }) {
  const mem = state.memory;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <Card icon={Target} label="Blast radius" accent="#ffb020">
        {state.blastRadius ? (
          <span className="text-[12px] leading-snug">{state.blastRadius}</span>
        ) : (
          dash
        )}
      </Card>

      <Card icon={GitCommitHorizontal} label="Probable cause" accent="#4d9fff">
        {state.probableCause ? (
          <>
            <span className="text-[12px] leading-snug">{state.probableCause}</span>
            {typeof state.confidence === "number" && <ConfidenceBar value={state.confidence} />}
          </>
        ) : (
          dash
        )}
      </Card>

      <Card icon={Brain} label="Memory" accent="#a78bfa">
        {mem && mem.times_seen != null ? (
          <span className="text-[12px] leading-snug">
            Seen <span className="font-semibold text-slate-100">{mem.times_seen}×</span>
            {mem.avg_resolution_minutes != null && (
              <> · avg <span className="font-mono text-slate-100">{mem.avg_resolution_minutes}m</span></>
            )}
            {mem.similarity != null && (
              <span className="ml-1 text-slate-500">({Math.round(mem.similarity * 100)}% match)</span>
            )}
          </span>
        ) : mem ? (
          <span className="text-slate-500">no strong prior</span>
        ) : (
          dash
        )}
      </Card>

      <Card icon={ShieldCheck} label="Remediation" accent="#3ddc97">
        {state.plan ? (
          <div className="flex flex-col gap-1">
            <span className="font-mono text-[12px] text-slate-100">
              {state.plan.action} → {state.plan.rollback_target ?? state.plan.target}
            </span>
            {state.decision && (
              <span
                className={`chip w-fit ${
                  state.decision === "approved"
                    ? "border-signal-green/30 bg-signal-green/10 text-signal-green"
                    : "border-signal-red/30 bg-signal-red/10 text-signal-red"
                }`}
              >
                {state.decision} {state.approver ? `· ${state.approver}` : ""}
              </span>
            )}
          </div>
        ) : (
          dash
        )}
      </Card>

      <Card icon={MessageSquareText} label="Comms" accent="#3ddc97">
        {state.comms ? (
          <div className="flex flex-col gap-0.5 text-[12px]">
            {state.comms.ticket_id && (
              <span className="font-mono text-slate-100">🎫 {state.comms.ticket_id}</span>
            )}
            {state.comms.slack_channel && (
              <span className="text-slate-400">{state.comms.slack_channel}</span>
            )}
            {state.comms.rca_present && (
              <span className="text-signal-green">RCA generated</span>
            )}
          </div>
        ) : (
          dash
        )}
      </Card>
    </div>
  );
}
