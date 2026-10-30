import { useState } from "react";
import { Activity, CheckCircle2, RefreshCw, Server, XCircle } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { EventRow, Job, ListenerRow, ToolStatus } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, PageHeader, Panel, Segmented, Stat, Terminal } from "@/components/ui";
import { formatDateTime, formatMs, timeAgo } from "@/lib/format";

export default function Monitoring() {
  const { system } = useApp();
  const [tab, setTab] = useState<"events" | "jobs" | "tools" | "listeners">("events");

  const events = useApi<{ events: EventRow[] }>("/activity?limit=150", { interval: 10000 });
  const jobList = useApi<{ jobs: Job[]; stats: Record<string, number> }>("/jobs?limit=40", { interval: 5000 });
  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools", { interval: 60000 });
  const listeners = useApi<{ listeners: ListenerRow[] }>("/listeners", { interval: 20000 });

  const stats = jobList.data?.stats ?? {};

  return (
    <div className="page">
      <PageHeader
        title="Monitoring"
        subtitle="Live job telemetry, platform events, toolchain and listener health"
        actions={
          <Button
            size="sm"
            onClick={() => {
              events.refresh();
              jobList.refresh();
              tools.refresh();
              listeners.refresh();
            }}
          >
            <RefreshCw size={12} /> Refresh all
          </Button>
        }
      />

      <div className="stat-grid">
        <Stat value={stats.running ?? 0} label="Jobs running" tone={stats.running ? "warn" : "ok"} />
        <Stat value={stats.succeeded ?? 0} label="Jobs succeeded" tone="ok" />
        <Stat value={stats.failed ?? 0} label="Jobs failed" tone={stats.failed ? "warn" : undefined} />
        <Stat value={system?.health.uptimeSeconds ? `${Math.floor(system.health.uptimeSeconds / 60)}m` : "—"} label="API uptime" />
      </div>

      <Panel
        title="Telemetry"
        actions={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "events", label: "Events" },
              { value: "jobs", label: "Jobs" },
              { value: "tools", label: "Tools" },
              { value: "listeners", label: "Listeners" },
            ]}
          />
        }
      >
        {tab === "events" && (
          events.data?.events.length ? (
            <div className="col" style={{ gap: 6, maxHeight: 480, overflowY: "auto" }}>
              {events.data.events.map((event) => (
                <div
                  key={event.id}
                  className="row"
                  style={{ gap: 10, padding: "7px 9px", borderBottom: "1px dashed var(--line-soft)" }}
                >
                  <span className="tiny mono mute" style={{ width: 130 }}>{formatDateTime(event.at * 1000)}</span>
                  <Badge tone={event.level === "warn" ? "warn" : event.level === "error" ? "err" : "dim"}>{event.kind}</Badge>
                  <span className="small td-truncate" style={{ flex: 1 }}>{event.title}</span>
                  <span className="tiny mute td-truncate" style={{ maxWidth: 280 }}>{event.detail}</span>
                </div>
              ))}
            </div>
          ) : <Empty icon={<Activity size={16} />} title="No platform events" detail="Events appear as you use the GUI." />
        )}

        {tab === "jobs" && (
          jobList.data?.jobs.length ? (
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Job</th><th>Kind</th><th>Status</th><th>Progress</th><th>Duration</th><th>Started</th></tr></thead>
                <tbody>
                  {jobList.data.jobs.map((job) => (
                    <tr key={job.id}>
                      <td className="mono tiny td-truncate">{job.title}</td>
                      <td><Badge tone="dim">{job.kind}</Badge></td>
                      <td><Badge tone={job.status === "succeeded" ? "ok" : job.status === "failed" ? "err" : job.status === "cancelled" ? "warn" : "info"}>{job.status}</Badge></td>
                      <td className="tiny mono">{(job.progress * 100).toFixed(0)}%</td>
                      <td className="tiny mono">{job.durationMs != null ? formatMs(job.durationMs) : "—"}</td>
                      <td className="tiny mute">{formatDateTime(job.createdAt * 1000)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <Empty title="No jobs recorded" />
        )}

        {tab === "tools" && (
          <div className="grid-3">
            {(tools.data?.tools ?? []).map((tool) => (
              <div className="cmd-card" key={tool.key} style={{ cursor: "default" }}>
                <div className="cmd-name">
                  <span className="row" style={{ gap: 7 }}>
                    {tool.available ? <CheckCircle2 size={13} className="green" /> : <XCircle size={13} className="red" />}
                    {tool.label}
                  </span>
                  <Badge tone={tool.available ? "ok" : tool.required === "yes" ? "err" : "dim"}>
                    {tool.available ? "ready" : "missing"}
                  </Badge>
                </div>
                <div className="cmd-desc">{tool.purpose}</div>
                <div className="tiny mono mute td-truncate">{tool.version ?? tool.path ?? "—"}</div>
              </div>
            ))}
          </div>
        )}

        {tab === "listeners" && (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Host</th><th>Port</th><th>State</th><th>Purpose</th></tr></thead>
              <tbody>
                {(listeners.data?.listeners ?? []).map((row) => (
                  <tr key={`${row.host}:${row.port}`}>
                    <td className="mono tiny">{row.host}</td>
                    <td className="mono">{row.port}</td>
                    <td><Badge tone={row.open ? "ok" : "dim"} dot>{row.open ? "open" : "closed"}</Badge></td>
                    <td className="tiny mute">{describePort(row.port)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {tab === "events" && (
        <Panel title="Environment" muted>
          <div className="grid-3">
            <div className="kv"><span className="kv-k">Hostname</span><span className="kv-v mono tiny">{system?.environment.hostname ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Local IP</span><span className="kv-v mono tiny">{system?.environment.localIp ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Python</span><span className="kv-v mono tiny">{system?.environment.python ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Platform</span><span className="kv-v mono tiny td-truncate">{system?.environment.platform ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Workspace</span><span className="kv-v mono tiny td-truncate">{system?.workspace.workspace ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Database</span><span className="kv-v mono tiny td-truncate">{system?.workspace.databasePath ?? "—"}</span></div>
          </div>
        </Panel>
      )}
    </div>
  );
}

function describePort(port: number): string {
  switch (port) {
    case 4444:
      return "meterpreter handler";
    case 5555:
      return "adb tcp transport";
    case 55553:
      return "metasploit RPC";
    case 8080:
      return "http proxy";
    case 8443:
      return "https proxy";
    case 5000:
      return "pegasus web api";
    default:
      return "—";
  }
}
