import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Health } from "./api";
import AgentGraph from "./components/AgentGraph";
import ApprovalModal from "./components/ApprovalModal";
import GrafanaPanel from "./components/GrafanaPanel";
import Header from "./components/Header";
import InsightStrip from "./components/InsightStrip";
import ReasoningStream from "./components/ReasoningStream";
import RcaTimeline from "./components/RcaTimeline";
import RegistryDrawer from "./components/RegistryDrawer";
import { useIncidentStream } from "./useIncidentStream";

export default function App() {
  const { state, conn } = useIncidentStream();
  const [health, setHealth] = useState<Health | null>(null);
  const [registryOpen, setRegistryOpen] = useState(false);
  const [firing, setFiring] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  // The modal is dismissed locally the instant the operator acts, so a late
  // `approved`/`rejected` replay can't pop it back open.
  const [modalDismissed, setModalDismissed] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  const toastTimer = useRef<ReturnType<typeof setTimeout>>();
  const flash = (msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  };

  const fireAlert = async () => {
    setFiring(true);
    try {
      await api.fireDemoAlert();
      flash("Alert published to the event bus — orchestrator engaging.");
    } catch (e) {
      flash(e instanceof Error ? e.message : "Failed to publish alert");
    } finally {
      setFiring(false);
    }
  };

  const modalOpen =
    !!state.incidentId &&
    !!state.plan &&
    state.status === "AWAITING_APPROVAL" &&
    !state.decision &&
    modalDismissed !== state.incidentId;

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        state={state}
        conn={conn}
        health={health}
        firing={firing}
        onFire={fireAlert}
        onOpenRegistry={() => setRegistryOpen(true)}
      />

      <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-4 px-4 py-5 lg:px-6">
        <AgentGraph state={state} />
        <InsightStrip state={state} />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="lg:col-span-5">
            <div className="h-[560px]">
              <ReasoningStream state={state} />
            </div>
          </div>
          <div className="lg:col-span-3">
            <div className="h-[560px]">
              <GrafanaPanel state={state} />
            </div>
          </div>
          <div className="lg:col-span-4">
            <div className="h-[560px]">
              <RcaTimeline state={state} />
            </div>
          </div>
        </div>

        <footer className="pb-6 pt-2 text-center text-[10.5px] text-slate-600">
          AegisOps · autonomous SRE on-call · six ADK sub-agents on{" "}
          <span className="font-mono">{health?.model ?? "gemini-3.5-flash"}</span> · human-gated
          remediation
        </footer>
      </main>

      {state.incidentId && state.plan && (
        <ApprovalModal
          incidentId={state.incidentId}
          plan={state.plan}
          open={modalOpen}
          onResolved={(d) => {
            setModalDismissed(state.incidentId);
            flash(d === "approved" ? "Approved — executor running." : "Remediation rejected.");
          }}
        />
      )}

      <RegistryDrawer open={registryOpen} onClose={() => setRegistryOpen(false)} />

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.96 }}
            className="fixed bottom-5 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-2 rounded-lg border border-white/10 bg-ink-800 px-4 py-2.5 text-[12.5px] text-slate-200 shadow-panel"
          >
            <AlertTriangle size={14} className="text-signal-amber" />
            {toast}
            <button onClick={() => setToast(null)} className="ml-1 text-slate-500 hover:text-slate-300">
              <X size={13} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
