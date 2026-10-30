import { useMemo, useState } from "react";
import { Play, Rocket, RefreshCw, RotateCcw } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job, WorkflowHistoryEntry } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Field, Modal, PageHeader, Panel, Progress, Terminal } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { formatDateTime, formatMs, titleCase } from "@/lib/format";

const STAGES = [
  { id: "recon", label: "Reconnaissance" },
  { id: "fingerprint", label: "Fingerprint" },
  { id: "vuln_assessment", label: "Vulnerability assessment" },
  { id: "exploit_selection", label: "Exploit selection" },
  { id: "exploit_execution", label: "Exploit execution" },
  { id: "access_establishment", label: "Access establishment" },
  { id: "persistence", label: "Persistence" },
  { id: "credential_extraction", label: "Credential extraction" },
  { id: "lateral_movement", label: "Lateral movement" },
  { id: "data_exfiltration", label: "Data exfiltration" },
  { id: "post_exploitation", label: "Post exploitation" },
  { id: "cleanup", label: "Cleanup" },
];

export default function WorkflowEngine() {
  const { activeSerial } = useApp();
  const [target, setTarget] = useState("");
  const [category, setCategory] = useState<"full_lifecycle" | "stage_by_stage">("full_lifecycle");
  const [stage, setStage] = useState("recon");
  const [jobId, setJobId] = useState<string | null>(null);
  const [inspect, setInspect] = useState<WorkflowHistoryEntry | null>(null);

  const history = useApi<{ history: WorkflowHistoryEntry[]; rates: Record<string, number> }>("/workflows", {
    interval: 15000,
  });

  const stats = useMemo(() => {
    const runs = history.data?.history ?? [];
    const wins = runs.filter((r) => r.overall_success).length;
    const avg =
      runs.length > 0
        ? runs.reduce((acc, run) => acc + (run.total_duration_ms ?? 0), 0) / runs.length
        : 0;
    return {
      runs: runs.length,
      wins,
      rate: runs.length ? Math.round((wins / runs.length) * 100) : null,
      avg,
    };
  }, [history.data]);

  const launch = async () => {
    const data = await api.post<{ job: Job }>("/workflows/run", {
      target: target || activeSerial || "127.0.0.1",
      category,
      stage: category === "stage_by_stage" ? stage : undefined,
    });
    setJobId(data.job.id);
    history.refresh();
  };

  return (
    <div className="page">
      <PageHeader
        title="Workflow Engine"
        subtitle="Autonomous lifecycle and guided stage-by-stage execution"
        actions={
          <Button size="sm" onClick={history.refresh}>
            <RefreshCw size={13} /> Refresh
          </Button>
        }
      />

      <div className="stat-grid">
        <div className="stat info">
          <div className="stat-value" style={{ fontSize: 20 }}>{stats.runs}</div>
          <div className="stat-label">Recorded runs</div>
          <div className="stat-hint">from workflow logger</div>
        </div>
        <div className="stat ok">
          <div className="stat-value" style={{ fontSize: 20 }}>{stats.wins}</div>
          <div className="stat-label">Successful</div>
          <div className="stat-hint">{stats.rate !== null ? `${stats.rate}% success` : "—"}</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ fontSize: 20 }}>{stats.avg ? formatMs(stats.avg) : "—"}</div>
          <div className="stat-label">Average duration</div>
          <div className="stat-hint">across recorded runs</div>
        </div>
        <div className="stat warn">
          <div className="stat-value" style={{ fontSize: 20 }}>{STAGES.length}</div>
          <div className="stat-label">Lifecycle stages</div>
          <div className="stat-hint">self-healing enabled</div>
        </div>
      </div>

      <Panel title="Launch run">
        <div className="form-row">
          <Field label="Target (IP / serial)">
            <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder={activeSerial ?? "192.168.1.105"} />
          </Field>
          <Field label="Category">
            <select className="select" value={category} onChange={(e) => setCategory(e.target.value as typeof category)}>
              <option value="full_lifecycle">Full lifecycle</option>
              <option value="stage_by_stage">Stage by stage</option>
            </select>
          </Field>
          <Field label="Start stage">
            <select
              className="select"
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              disabled={category !== "stage_by_stage"}
            >
              {STAGES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </Field>
          <Field label="Dispatch">
            <button className="btn btn-primary" onClick={() => void launch()}>
              <Rocket size={13} /> Start workflow
            </button>
          </Field>
        </div>
        <div className="tiny mute" style={{ marginTop: 10 }}>
          Full lifecycle runs every stage sequentially with adaptive decisions. Stage-by-stage runs
          resume from your chosen checkpoint and return a recommendation for the next stage.
        </div>
      </Panel>

      {jobId && (
        <Panel title="Live run">
          <JobOutput jobId={jobId} title="workflow execution" height={360} />
        </Panel>
      )}

      <div className="grid-2">
        <Panel title="Run history" tight>
          {!history.data?.history.length ? (
            <Empty icon={<Play size={16} />} title="No runs yet" detail="Launch a workflow to populate history." />
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr><th>Run</th><th>Target</th><th>Mode</th><th>Stages</th><th>Result</th><th>Duration</th><th /></tr>
                </thead>
                <tbody>
                  {history.data.history.slice().reverse().map((run, index) => (
                    <tr key={run.run_id ?? index}>
                      <td className="mono tiny td-truncate">{run.run_id?.slice(0, 12) ?? "—"}</td>
                      <td className="td-truncate">{run.target ?? "—"}</td>
                      <td className="tiny">{titleCase(run.category ?? "—")}</td>
                      <td className="tiny mono">{run.stages?.length ?? 0}</td>
                      <td><Badge tone={run.overall_success ? "ok" : "err"}>{run.overall_success ? "success" : "failed"}</Badge></td>
                      <td className="tiny mono">{run.total_duration_ms ? formatMs(run.total_duration_ms) : "—"}</td>
                      <td><Button size="xs" onClick={() => setInspect(run)}>inspect</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Success rate by vector">
          {!history.data?.rates || !Object.keys(history.data.rates).length ? (
            <Empty title="No exploit telemetry" detail="Vector rates appear once exploit attempts are logged." />
          ) : (
            <div className="col" style={{ gap: 10 }}>
              {Object.entries(history.data.rates).sort((a, b) => b[1] - a[1]).map(([vector, rate]) => (
                <div className="meter" key={vector}>
                  <span className="tiny mono" style={{ width: 96 }}>{titleCase(vector)}</span>
                  <Progress value={rate} thin />
                  <span className="tiny mono" style={{ width: 40, textAlign: "right" }}>{rate.toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Lifecycle stages" muted>
        <div className="grid-4">
          {STAGES.map((item, index) => (
            <div className="cmd-card" key={item.id} style={{ cursor: "default", gap: 4 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="tiny mono mute">{String(index + 1).padStart(2, "0")}</span>
                <span className="tiny mono">{item.id}</span>
              </div>
              <div className="small">{item.label}</div>
            </div>
          ))}
        </div>
      </Panel>

      {inspect && (
        <Modal title={`Run ${inspect.run_id?.slice(0, 12) ?? ""}`} onClose={() => setInspect(null)} width={760}>
          <div className="kv"><span className="kv-k">Target</span><span className="kv-v mono">{inspect.target ?? "—"}</span></div>
          <div className="kv"><span className="kv-k">Category</span><span className="kv-v">{inspect.category ?? "—"}</span></div>
          <div className="kv"><span className="kv-k">Started</span><span className="kv-v">{inspect.start_time ? formatDateTime(inspect.start_time) : "—"}</span></div>
          <div className="kv"><span className="kv-k">Result</span><span className="kv-v"><Badge tone={inspect.overall_success ? "ok" : "err"}>{inspect.overall_success ? "success" : "failed"}</Badge></span></div>
          <div className="kv"><span className="kv-k">Duration</span><span className="kv-v">{inspect.total_duration_ms ? formatMs(inspect.total_duration_ms) : "—"}</span></div>
          <Terminal lines={JSON.stringify(inspect.stages ?? [], null, 2)} title="stage results" maxHeight={320} />
        </Modal>
      )}
    </div>
  );
}
