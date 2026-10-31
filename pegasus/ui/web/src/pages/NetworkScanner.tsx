import { useState } from "react";
import { Network, Radar, RefreshCw, ShieldAlert, Wifi } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job, ListenerRow, ToolStatus } from "@/lib/types";
import { Badge, Button, Empty, Field, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

interface NmapHost {
  host: string;
  ports: { port: number; protocol: string; state: string; service: string }[];
}

export default function NetworkScanner() {
  const [tab, setTab] = useState<"nmap" | "listeners" | "tunnels">("nmap");
  const [target, setTarget] = useState("192.168.1.0/24");
  const [ports, setPorts] = useState("1-1000");
  const [jobId, setJobId] = useState<string | null>(null);
  const [hosts, setHosts] = useState<NmapHost[]>([]);

  const listeners = useApi<{ listeners: ListenerRow[] }>("/listeners", { interval: 20000 });
  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools");
  const nmap = (tools.data?.tools ?? []).find((tool) => tool.key === "nmap");
  const ngrok = (tools.data?.tools ?? []).find((tool) => tool.key === "ngrok");

  const scan = async () => {
    const data = await api.post<{ job: Job }>("/network/scan", { target, ports });
    setJobId(data.job.id);
  };

  const onDone = (job: Job) => {
    const result = job.result as { hosts?: NmapHost[] } | null;
    if (result?.hosts) setHosts(result.hosts);
  };

  const dispatchTool = async (tool: string, args: string[]) => {
    const data = await api.post<{ job: Job }>(`/tools/${tool}/run`, { args });
    setJobId(data.job.id);
  };

  return (
    <div className="page">
      <PageHeader
        title="Network Scanner"
        subtitle="nmap discovery, listener health and tunnel management"
        actions={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "nmap", label: "nmap", icon: <Network size={12} /> },
              { value: "listeners", label: "Listeners", icon: <Radar size={12} /> },
              { value: "tunnels", label: "Tunnels", icon: <Wifi size={12} /> },
            ]}
          />
        }
      />

      <div className="stat-grid">
        <Stat value={nmap?.available ? "READY" : "MISSING"} label="nmap" hint={nmap?.version ?? "not on PATH"} tone={nmap?.available ? "ok" : "warn"} />
        <Stat value={listeners.data?.listeners.filter((l) => l.open).length ?? "—"} label="Open local ports" tone="info" />
        <Stat value={hosts.length} label="Hosts discovered" hint="from last scan" />
        <Stat value={ngrok?.available ? "READY" : "MISSING"} label="ngrok" hint={ngrok?.version ?? "not on PATH"} />
      </div>

      {tab === "nmap" && (
        <>
          <Panel title="Scan configuration">
            <div className="form-row">
              <Field label="Target range">
                <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.0/24" />
              </Field>
              <Field label="Ports">
                <input className="input" value={ports} onChange={(e) => setPorts(e.target.value)} placeholder="1-1000" />
              </Field>
              <Field label="Launch">
                <button className="btn btn-primary" onClick={() => void scan()}>
                  <Radar size={13} /> Scan network
                </button>
              </Field>
            </div>
            <div className="tiny mute" style={{ marginTop: 8 }}>
              Uses <code>nmap -sV -T4</code>. Full output is captured in the job terminal; parsed hosts
              render below.
            </div>
          </Panel>

          {hosts.length > 0 && (
            <Panel title={`Discovered hosts (${hosts.length})`} tight>
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>Host</th><th>Open ports</th><th>Services</th></tr></thead>
                  <tbody>
                    {hosts.map((host) => {
                      const open = host.ports.filter((p) => p.state === "open");
                      return (
                        <tr key={host.host}>
                          <td className="mono td-strong">{host.host}</td>
                          <td className="mono tiny">{open.map((p) => `${p.port}/${p.protocol}`).join(", ") || "none"}</td>
                          <td className="tiny mute">{open.map((p) => p.service).filter(Boolean).join(", ") || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {jobId && (
            <Panel title="Scan output">
              <JobOutput jobId={jobId} title="nmap" height={340} onDone={onDone} />
            </Panel>
          )}
        </>
      )}

      {tab === "listeners" && (
        <Panel title="Listener health" tight actions={<Button size="sm" onClick={listeners.refresh}><RefreshCw size={12} /> Refresh</Button>}>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Host</th><th>Port</th><th>State</th><th>Expected service</th></tr></thead>
              <tbody>
                {(listeners.data?.listeners ?? []).map((row) => (
                  <tr key={`${row.host}:${row.port}`}>
                    <td className="mono tiny">{row.host}</td>
                    <td className="mono td-strong">{row.port}</td>
                    <td><Badge tone={row.open ? "ok" : "dim"} dot>{row.open ? "listening" : "closed"}</Badge></td>
                    <td className="tiny mute">{describePort(row.port)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {tab === "tunnels" && (
        <>
          <Panel title="Tunnel tooling">
            <div className="grid-3">
              {[
                { tool: "ngrok", args: ["http", "4444"], label: "Expose HTTP:4444", detail: "ngrok http 4444" },
                { tool: "ngrok", args: ["tcp", "4444"], label: "Expose TCP:4444", detail: "ngrok tcp 4444" },
                { tool: "openssl", args: ["version"], label: "OpenSSL version", detail: "certificate + crypto toolchain" },
              ].map((item) => (
                <button key={item.label} className="cmd-card" onClick={() => void dispatchTool(item.tool, item.args)}>
                  <div className="cmd-name"><span>{item.label}</span><Wifi size={12} /></div>
                  <div className="cmd-desc mono tiny">{item.detail}</div>
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="Tunnel guidance" muted>
            <div className="col" style={{ gap: 0 }}>
              <div className="kv"><span className="kv-k">Reverse SSH</span><span className="kv-v mono tiny">ssh -R 4444:localhost:4444 user@relay</span></div>
              <div className="kv"><span className="kv-k">Local forward</span><span className="kv-v mono tiny">ssh -L 5555:device:5555 user@jump</span></div>
              <div className="kv"><span className="kv-k">socat bridge</span><span className="kv-v mono tiny">socat TCP-LISTEN:4444,fork TCP:target:4444</span></div>
              <div className="kv"><span className="kv-k">ngrok</span><span className="kv-v mono tiny">ngrok tcp 4444</span></div>
            </div>
          </Panel>
          {jobId && (
            <Panel title="Tunnel output">
              <JobOutput jobId={jobId} title="tunnel" height={280} />
            </Panel>
          )}
        </>
      )}
    </div>
  );
}

function describePort(port: number): string {
  switch (port) {
    case 4444:
      return "meterpreter handler";
    case 5555:
      return "adb transport";
    case 55553:
      return "metasploit RPC";
    case 8080:
    case 8443:
      return "http(s) proxy";
    case 5001:
      return "pegasus api";
    default:
      return "unknown";
  }
}
