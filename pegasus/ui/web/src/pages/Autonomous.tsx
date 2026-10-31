import { useEffect, useRef, useState } from "react";
import { Loader2, Play, Radio, ShieldCheck, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge, Button, Modal, PageHeader, Panel, Stat, Terminal } from "@/components/ui";

interface LogEntry { at: number; msg: string }
interface RunState {
  run_id: string;
  state: string;
  created: number;
  devices: { serial: string; model: string; state: string }[];
  target: string | null;
  vector: string | null;
  post_exploit: Record<string, any> | null;
  log: LogEntry[];
  result?: any;
}

const STATE_LABEL: Record<string, string> = {
  discovery: "Discovery", triage: "Triage", craft_payload: "Crafting payload",
  deliver: "Delivering", listener_up: "Listener up", post_exploit: "Post-exploit",
  notify: "Notifying", awaiting_decision: "Awaiting decision",
  complete: "Complete", aborted: "Aborted", wiped: "Wiped",
};

export default function Autonomous() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [starting, setStarting] = useState(false);
  const [decided, setDecided] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const start = async () => {
    setStarting(true);
    setDecided(null);
    try {
      const r = await api.post<{ run_id: string }>("/autonomous/start", {});
      setRunId(r.run_id);
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    if (!runId) return;
    let stop = false;
    const tick = async () => {
      try {
        const r = await api.get<RunState>(`/autonomous/${runId}`);
        if (!stop) setRun(r);
        if (!["complete", "aborted", "wiped"].includes(r.state)) {
          window.setTimeout(tick, 2000);
          return;
        }
      } catch {
        if (!stop) window.setTimeout(tick, 3000);
      }
    };
    void tick();
    return () => { stop = true; };
  }, [runId]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [run?.log?.length]);

  const decide = async (action: "maintain" | "wipe" | "abort") => {
    if (!runId) return;
    const r = await api.post<RunState>(`/autonomous/${runId}/decision`, { action });
    setDecided(action);
    setRun((prev) => (prev ? { ...prev, state: r.state } : prev));
  };

  const stateTone = (s: string) =>
    s === "complete" || s === "wiped" ? "ok" : s === "aborted" ? "warn" : "info";

  return (
    <div className="page">
      <PageHeader
        title="Autonomous Lifecycle"
        subtitle="Scan → triage → craft → deliver → post-exploit → decide — fully automated"
        actions={
          <Button onClick={() => void start()} disabled={starting || (run?.state ?? "") === "awaiting_decision"}>
            {starting ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />} Start run
          </Button>
        }
      />

      <div className="stat-grid">
        <Stat value={run ? STATE_LABEL[run.state] ?? run.state : "idle"} label="State" tone={run ? stateTone(run.state) : undefined} />
        <Stat value={run?.devices?.length ?? 0} label="Devices found" />
        <Stat value={run?.target ?? "—"} label="Target" hint={run?.vector ?? undefined} />
        <Stat value={run?.post_exploit ? Object.keys(run.post_exploit).length : 0} label="Post-exploit modules" />
      </div>

      {run && (
        <Panel title="Live log" actions={<Badge tone={stateTone(run.state)}>{run.run_id}</Badge>}>
          <div ref={logRef} style={{ maxHeight: 420, overflowY: "auto" }}>
            <Terminal lines={(run.log ?? []).map((l) => ({ text: l.msg }))} />
          </div>
        </Panel>
      )}

      {run?.state === "awaiting_decision" && !decided && (
        <Modal
          open
          onClose={() => { /* decision required */ }}
          title="Automated attack lifecycle complete"
        >
          <p className="tiny mute">
            The full lifecycle finished on <span className="mono">{run?.target}</span> via{" "}
            <span className="mono">{run?.vector}</span>. Post-exploit ran{" "}
            {run?.post_exploit ? Object.keys(run.post_exploit).length : 0} modules.
          </p>
          <div className="row" style={{ gap: 10, marginTop: 16 }}>
            <Button onClick={() => void decide("maintain")}>
              <ShieldCheck size={13} /> Maintain connection
            </Button>
            <Button variant="ghost" onClick={() => void decide("wipe")}>
              <Trash2 size={13} /> Wipe logs and disconnect
            </Button>
            <Button variant="ghost" onClick={() => void decide("abort")}>
              <Radio size={13} /> Abort
            </Button>
          </div>
        </Modal>
      )}

      {decided && (
        <Panel title="Decision recorded">
          <span className="tiny mute">
            {decided === "maintain" && "Connection maintained — the session stays live."}
            {decided === "wipe" && "Logs wiped and connection dropped."}
            {decided === "abort" && "Run aborted."}
          </span>
        </Panel>
      )}
    </div>
  );
}
