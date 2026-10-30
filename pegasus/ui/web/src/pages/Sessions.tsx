import { useState } from "react";
import { Activity, RefreshCw, Terminal } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

const SESSION_COMMANDS = [
  { command: "sessions", label: "List sessions", detail: "Enumerate active Meterpreter sessions" },
  { command: "auto-fetch", label: "Auto-fetch", detail: "Poll RPC for newly created sessions" },
  { command: "keepalive", label: "Keepalive", detail: "Maintain session liveness" },
  { command: "session-info", label: "Session info", detail: "Detailed metadata for a session" },
  { command: "session-command", label: "Run command", detail: "Execute inside a session" },
];

export default function Sessions() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [info, setInfo] = useState("");
  const [sessionId, setSessionId] = useState("1");
  const [command, setCommand] = useState("getuid");

  const system = useApi<{ workspace: { metasploit: string } }>("/system");

  const dispatch = async (name: string, args: string[] = []) => {
    const data = await api.post<{ job: Job }>(`/commands/${name}/run`, { args });
    setJobId(data.job.id);
  };

  return (
    <div className="page">
      <PageHeader
        title="Sessions"
        subtitle="Metasploit RPC session management"
        actions={<Button size="sm" onClick={() => void dispatch("sessions")}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={system.data?.workspace.metasploit ?? "—"} label="RPC endpoint" tone="info" />
        <Stat value="msgrpc" label="Transport" hint="pymetasploit3 JSON-RPC" />
        <Stat value="60s" label="Keepalive default" />
        <Stat value="poll" label="Auto-fetch mode" hint="background discovery" />
      </div>

      <div className="grid-2">
        <Panel title="Session operations">
          <div className="col" style={{ gap: 8 }}>
            {SESSION_COMMANDS.map((item) => (
              <div className="cmd-card" key={item.command} style={{ flexDirection: "row", alignItems: "center", gap: 10, cursor: "default" }}>
                <Terminal size={13} />
                <div style={{ flex: 1 }}>
                  <div className="cmd-name" style={{ marginBottom: 2 }}>{item.label}</div>
                  <div className="cmd-desc">{item.detail}</div>
                </div>
                <Button size="xs" onClick={() => void dispatch(item.command)}>run</Button>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Session console">
          <div className="form-row">
            <Field label="Session id">
              <input className="input" value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
            </Field>
            <Field label="Command">
              <input className="input" value={command} onChange={(e) => setCommand(e.target.value)} />
            </Field>
            <Field label="Execute">
              <button className="btn btn-primary" onClick={() => void dispatch("session-command", [sessionId, command])}>
                Send
              </button>
            </Field>
          </div>
          <div className="tiny mute" style={{ marginTop: 12 }}>
            Use <code>sessions</code> first to enumerate ids, then dispatch commands by id. RPC
            credentials come from <code>PEGASUS__METASPLOIT__RPC_PASSWORD</code>.
          </div>
          <div className="kv" style={{ marginTop: 12 }}>
            <span className="kv-k">Endpoint</span>
            <span className="kv-v mono tiny">{system.data?.workspace.metasploit ?? "—"}</span>
          </div>
          <div className="kv"><span className="kv-k">Transport</span><span className="kv-v mono tiny">msgpack over TLS opt.</span></div>
        </Panel>
      </div>

      {jobId ? (
        <Panel title="Session output">
          <JobOutput jobId={jobId} title="metasploit" height={320} />
        </Panel>
      ) : (
        <Panel title="Awaiting command" muted>
          <Empty icon={<Activity size={16} />} title="No session command dispatched" detail="Pick an operation to inspect output." />
        </Panel>
      )}
    </div>
  );
}
