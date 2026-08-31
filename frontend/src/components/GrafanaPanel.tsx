import { motion } from "framer-motion";
import { CheckCircle2, Eye, ImageOff, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import type { WarRoomState } from "../types";
import { Empty, PanelTitle, Spinner } from "./ui";

export default function GrafanaPanel({ state }: { state: WarRoomState }) {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const id = state.incidentId;
  const vision = state.vision;

  const confirmed = vision?.confirmed;
  const confirmChip =
    confirmed === true ? (
      <span className="chip border-signal-green/40 bg-signal-green/10 text-signal-green">
        <CheckCircle2 size={12} /> confirmed
      </span>
    ) : confirmed === false ? (
      <span className="chip border-signal-red/40 bg-signal-red/10 text-signal-red">
        <XCircle size={12} /> not confirmed
      </span>
    ) : null;

  return (
    <section className="panel flex min-h-0 flex-col">
      <PanelTitle icon={<Eye size={15} className="text-signal-violet" />} right={confirmChip}>
        Grafana Snapshot · Vision
      </PanelTitle>

      {!id ? (
        <Empty>
          <ImageOff size={20} className="text-slate-600" />
          <div>No snapshot loaded.</div>
        </Empty>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col p-3">
          <div className="relative overflow-hidden rounded-lg border border-white/10 bg-black/40">
            {status === "loading" && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-ink-900/60">
                <Spinner />
              </div>
            )}
            {status === "error" ? (
              <div className="flex h-40 flex-col items-center justify-center gap-2 text-xs text-slate-500">
                <ImageOff size={20} />
                Snapshot unavailable
              </div>
            ) : (
              <>
                <img
                  src={api.grafanaUrl(id)}
                  alt="Grafana dashboard analyzed by the vision agent"
                  className="block w-full object-contain"
                  onLoad={() => setStatus("ok")}
                  onError={() => setStatus("error")}
                />
                {/* AI annotation overlaid on the exact image vision read */}
                {vision?.annotation && status === "ok" && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="absolute inset-x-2 bottom-2 rounded-md border border-signal-violet/40 bg-ink-950/85 px-3 py-2 backdrop-blur-sm"
                  >
                    <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-signal-violet">
                      <Eye size={11} /> AI annotation
                    </div>
                    <div className="mt-0.5 font-mono text-[11.5px] text-slate-100">
                      {vision.annotation}
                    </div>
                  </motion.div>
                )}
              </>
            )}
          </div>

          <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
            {vision?.observation ? (
              <div className="rounded-md border border-white/[0.06] bg-ink-900/40 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                  Vision observation
                </div>
                <p className="mt-1 font-mono text-[11.5px] leading-relaxed text-slate-300">
                  {vision.observation}
                </p>
              </div>
            ) : (
              <p className="px-1 text-[11px] text-slate-500">
                Waiting for the Diagnosis agent to read this dashboard with Gemini vision…
              </p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
