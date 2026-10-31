import { useEffect, useMemo, useState } from "react";
import { Copy, Download, FileText, Loader2, RefreshCw, ScrollText } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat, Terminal } from "@/components/ui";
import { formatBytes, formatDateTime, timeAgo } from "@/lib/format";

interface LogFile {
  id: string;
  name: string;
  dir: string;
  size: number;
  modified: number;
}

interface LogContent {
  id: string;
  name: string;
  size: number;
  modified: number;
  totalLines: number;
  content: string;
}

export default function Logs() {
  const index = useApi<{ logs: LogFile[]; count: number; directory: string }>("/logs", { interval: 30000 });
  const [selected, setSelected] = useState<string | null>(null);
  const [log, setLog] = useState<LogContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [search, setSearch] = useState("");

  const load = async (id: string) => {
    setSelected(id);
    setLoading(true);
    setError(null);
    setLog(null);
    try {
      const r = await api.get<LogContent>(`/logs/${id}`);
      setLog(r);
    } catch (e: any) {
      setError(e?.message ?? "failed to load log");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!selected && index.data?.logs?.length) {
      void load(index.data.logs[0].id);
    }
  }, [index.data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return index.data?.logs ?? [];
    return (index.data?.logs ?? []).filter(
      (f) => f.id.toLowerCase().includes(q) || f.name.toLowerCase().includes(q),
    );
  }, [index.data, search]);

  const copy = async () => {
    if (!log?.content) return;
    try {
      await navigator.clipboard.writeText(log.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked */
    }
  };

  const download = (url: string) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="page">
      <PageHeader
        title="Logs"
        subtitle="Full activity, scan and daemon logs — view, copy, download"
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={() => void index.refresh()}>
              <RefreshCw size={12} /> Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => download("/api/logs/combined/download")}
              title="Download every log concatenated into one file"
            >
              <Download size={12} /> Download all
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={index.data?.count ?? "—"} label="Log files" />
        <Stat value={selected ? (log?.totalLines ?? "—") : "—"} label="Lines in view" />
        <Stat value={log ? formatBytes(log.size) : "—"} label="Size in view" />
        <Stat value={index.data?.directory ?? "—"} label="Directory" hint="~/.pegasus/logs" />
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: "280px 1fr", gap: 12, alignItems: "start" }}>
        <Panel title="Files" tight>
          <div style={{ padding: "6px 8px" }}>
            <input
              className="input mono tiny"
              style={{ width: "100%" }}
              placeholder="filter…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div style={{ maxHeight: 460, overflowY: "auto" }}>
            {index.loading && !index.data ? (
              <div style={{ padding: 16 }}><Loader2 size={14} className="animate-spin" /></div>
            ) : filtered.length === 0 ? (
              <Empty icon={<FileText size={16} />} title="No logs yet" detail="Run a scan or command — output lands here." />
            ) : (
              filtered.map((f) => (
                <div
                  key={f.id}
                  onClick={() => void load(f.id)}
                  className="row"
                  style={{
                    gap: 8,
                    padding: "7px 10px",
                    cursor: "pointer",
                    background: selected === f.id ? "rgba(88,166,255,.08)" : "transparent",
                    borderLeft: selected === f.id ? "2px solid #58a6ff" : "2px solid transparent",
                    alignItems: "center",
                  }}
                >
                  <ScrollText size={12} className="mute" />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="mono tiny td-truncate">{f.name}</div>
                    <div className="tiny mute">{f.dir.replace(/^C:.*\.pegasus/, "~/.pegasus")}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="tiny mute">{formatBytes(f.size)}</div>
                    <div className="tiny mute">{timeAgo(f.modified)}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </Panel>

        <Panel
          title={selected ? selected : "Viewer"}
          actions={
            <>
              {log && (
                <Badge tone="dim">
                  {log.totalLines} lines · {formatBytes(log.size)} · {formatDateTime(log.modified)}
                </Badge>
              )}
              <Button size="sm" variant="ghost" onClick={() => void copy()} disabled={!log?.content}>
                <Copy size={12} /> {copied ? "copied" : "copy"}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => selected && download(`/api/logs/${selected}/download`)}
                disabled={!selected}
              >
                <Download size={12} /> download
              </Button>
            </>
          }
        >
          {loading ? (
            <div style={{ padding: 24, textAlign: "center" }}>
              <Loader2 size={16} className="animate-spin" />
            </div>
          ) : error ? (
            <Empty icon={<FileText size={16} />} title="Could not read log" detail={error} />
          ) : !log ? (
            <Empty icon={<FileText size={16} />} title="Select a file" detail="Pick a log on the left to view it." />
          ) : (
            <Terminal
              title={log.name}
              lines={log.content}
              maxHeight={460}
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
