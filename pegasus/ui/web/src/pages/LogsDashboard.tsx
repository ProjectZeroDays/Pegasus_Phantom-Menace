import { useMemo, useState } from "react";
import { Activity, AlertTriangle, BarChart3, FileText, RefreshCw, Search, TrendingUp } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { formatBytes, formatDateTime, timeAgo } from "@/lib/format";

interface DashboardFile {
  id: string;
  name: string;
  dir: string;
  size: number;
  modified: number;
}

interface TimelineEntry {
  ts: string;
  event: string;
  status: string;
  note: string;
  file: string;
  level: string;
}

interface TopCategory {
  name: string;
  count: number;
}

interface DashboardPayload {
  directory: string;
  eventsFile: string;
  fileCount: number;
  totalBytes: number;
  total: number;
  categories: Record<string, number>;
  levels: Record<string, number>;
  statuses: Record<string, number>;
  topCategories: TopCategory[];
  timeline: TimelineEntry[];
  files: DashboardFile[];
}

const LEVEL_TONE: Record<string, "ok" | "warn" | "err" | "info" | "dim"> = {
  critical: "err",
  error: "err",
  warning: "warn",
  info: "info",
  debug: "dim",
};

const LEVEL_COLOR: Record<string, string> = {
  critical: "var(--err)",
  error: "var(--err)",
  warning: "var(--warn)",
  info: "var(--info)",
  debug: "var(--ink-mute)",
};

export default function LogsDashboard() {
  const [filter, setFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState<string>("all");

  const dash = useApi<DashboardPayload>("/logs/dashboard", { interval: 10000 });

  const d = dash.data;
  const levels = d?.levels ?? {};
  const top = d?.topCategories ?? [];
  const maxTop = top.length ? Math.max(...top.map((t) => t.count)) : 0;
  const levelTotal = Object.values(levels).reduce((a, b) => a + b, 0) || 1;

  const timeline = useMemo(() => {
    const rows = d?.timeline ?? [];
    const q = filter.trim().toLowerCase();
    return rows.filter((row) => {
      if (levelFilter !== "all" && row.level !== levelFilter) return false;
      if (!q) return true;
      return (
        row.event.toLowerCase().includes(q) ||
        row.note.toLowerCase().includes(q) ||
        row.status.toLowerCase().includes(q) ||
        row.file.toLowerCase().includes(q)
      );
    });
  }, [d?.timeline, filter, levelFilter]);

  const exportJson = async () => {
    const payload = JSON.stringify(d ?? {}, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "pegasus-logs-dashboard.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const levelChips = ["all", "critical", "error", "warning", "info", "debug"];

  return (
    <div className="page">
      <PageHeader
        title="Logs Dashboard"
        subtitle="Live event stream, severity mix and log-file health across the workspace"
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={dash.refresh}>
              <RefreshCw size={12} /> Refresh
            </Button>
            <Button size="sm" variant="ghost" onClick={() => void exportJson()} disabled={!d}>
              <BarChart3 size={12} /> Export
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={d?.total ?? "—"} label="Events" tone="info" />
        <Stat value={d?.fileCount ?? "—"} label="Log files" tone="info" hint={d ? formatBytes(d.totalBytes) : undefined} />
        <Stat value={levels.critical ?? 0} label="Critical" tone="warn" />
        <Stat value={levels.warning ?? 0} label="Warnings" tone="warn" />
      </div>

      <div className="split">
        <Panel title="Severity mix" actions={<span className="tiny mute">{levelTotal} classified</span>}>
          {levelTotal <= 1 && !d?.total ? (
            <Empty icon={<Activity size={16} />} title="No events yet" detail="Run a scan or command — events stream into the workspace log." />
          ) : (
            <>
              <div style={{ display: "flex", height: 10, borderRadius: 999, overflow: "hidden", background: "var(--surface-3)" }}>
                {["critical", "error", "warning", "info", "debug"].map((lv) => {
                  const v = levels[lv] ?? 0;
                  if (!v) return null;
                  return (
                    <div
                      key={lv}
                      title={`${lv}: ${v}`}
                      style={{ width: `${(v / levelTotal) * 100}%`, background: LEVEL_COLOR[lv] }}
                    />
                  );
                })}
              </div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 10 }}>
                {["critical", "error", "warning", "info", "debug"].map((lv) => (
                  <span key={lv} className="tiny row" style={{ gap: 6 }}>
                    <span className="dot" style={{ background: LEVEL_COLOR[lv], width: 7, height: 7, borderRadius: 999 }} />
                    <span className="mute">{lv}</span>
                    <strong className="mono">{levels[lv] ?? 0}</strong>
                  </span>
                ))}
              </div>
            </>
          )}
        </Panel>

        <Panel title="Top event categories">
          {top.length === 0 ? (
            <Empty icon={<TrendingUp size={16} />} title="No categories" detail="Categories appear once events are recorded." />
          ) : (
            top.map((t) => (
              <div key={t.name} className="meter-row">
                <div className="meter-label" style={{ width: 180 }}>{t.name}</div>
                <div className="meter-track">
                  <div className="meter-fill" style={{ width: `${maxTop ? (t.count / maxTop) * 100 : 0}%`, background: "var(--info)" }} />
                </div>
                <div className="meter-val">{t.count}</div>
              </div>
            ))
          )}
        </Panel>
      </div>

      <Panel
        title="Event timeline"
        actions={
          <div className="row" style={{ gap: 6 }}>
            {levelChips.map((lv) => (
              <button
                key={lv}
                className={`btn btn-xs ${levelFilter === lv ? "btn-primary" : ""}`}
                onClick={() => setLevelFilter(lv)}
              >
                {lv}
              </button>
            ))}
          </div>
        }
        tight
      >
        <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)" }}>
          <Field label="Filter events">
            <input
              className="input"
              placeholder="event, status, note or file…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </Field>
        </div>
        {timeline.length === 0 ? (
          <Empty icon={<Search size={16} />} title="Nothing to show" detail="No events match the current filter." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>When</th><th>Level</th><th>Event</th><th>Status</th><th>Detail</th></tr>
              </thead>
              <tbody>
                {timeline.slice(0, 200).map((row, i) => (
                  <tr key={`${row.ts}-${i}`}>
                    <td className="mono tiny">{row.ts ? formatDateTime(Date.parse(row.ts) || 0) : "—"}</td>
                    <td><Badge tone={LEVEL_TONE[row.level] ?? "dim"}>{row.level}</Badge></td>
                    <td className="td-strong td-truncate">{row.event}</td>
                    <td className="tiny mono">{row.status || "—"}</td>
                    <td className="tiny mute td-truncate">{row.note || row.file || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Log files" tight>
        {(d?.files ?? []).length === 0 ? (
          <Empty icon={<FileText size={16} />} title="No log files" detail="The workspace log directory is empty." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>File</th><th>Size</th><th>Modified</th><th /></tr></thead>
              <tbody>
                {(d?.files ?? []).map((f) => (
                  <tr key={f.id}>
                    <td className="td-strong mono tiny td-truncate">{f.id}</td>
                    <td className="mono tiny">{formatBytes(f.size)}</td>
                    <td className="tiny mute">{timeAgo(f.modified)}</td>
                    <td>
                      <a className="btn btn-xs" href={`/api/logs/${encodeURIComponent(f.id)}/download`}>
                        download
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="split">
        <Panel title="Statuses">
          {Object.keys(d?.statuses ?? {}).length === 0 ? (
            <Empty icon={<AlertTriangle size={16} />} title="No status labels" detail="Events without a status field are classified by level." />
          ) : (
            Object.entries(d?.statuses ?? {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="meter-row">
                <div className="meter-label" style={{ width: 140 }}>{k}</div>
                <div className="meter-track">
                  <div className="meter-fill" style={{ width: `${Math.min(100, v * 10)}%`, background: "var(--signal)" }} />
                </div>
                <div className="meter-val">{v}</div>
              </div>
            ))
          )}
        </Panel>

        <Panel title="Source">
          <div className="tiny" style={{ lineHeight: 1.9 }}>
            <div><span className="mute">events file</span><br /><code className="td-truncate">{d?.eventsFile || "—"}</code></div>
            <div style={{ marginTop: 8 }}><span className="mute">log directory</span><br /><code className="td-truncate">{d?.directory || "—"}</code></div>
            <div style={{ marginTop: 8 }}><span className="mute">distinct categories</span><br /><strong className="mono">{Object.keys(d?.categories ?? {}).length}</strong></div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
