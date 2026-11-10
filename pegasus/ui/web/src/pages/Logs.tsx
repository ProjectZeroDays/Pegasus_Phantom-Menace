import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Activity, AlertTriangle, ChevronRight, Copy, Download, FileText, Filter, GitCompare,
  Loader2, RefreshCw, Radio, ScrollText, Search, Trash2, X,
} from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
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

interface DashboardPayload {
  total: number;
  levels: Record<string, number>;
  categories: Record<string, number>;
  topCategories: { name: string; count: number }[];
  timeline: { ts: string; event: string; status: string; note: string; level: string }[];
  directory: string;
  eventsFile: string;
}

type Level = "critical" | "error" | "warning" | "info" | "debug";
const LEVELS: Level[] = ["critical", "error", "warning", "info", "debug"];
const LEVEL_COLOR: Record<Level, string> = {
  critical: "#f85149", error: "#f85149", warning: "#d29922", info: "#58a6ff", debug: "#6e7681",
};
const LEVEL_TONE: Record<Level, "ok" | "warn" | "err" | "info" | "dim"> = {
  critical: "err", error: "err", warning: "warn", info: "info", debug: "dim",
};

const LEVEL_RE = /\b(CRITICAL|FATAL|ERROR|WARNING|WARN|INFO|DEBUG|TRACE)\b/;

function detectLevel(line: string): Level {
  const m = LEVEL_RE.exec(line.toUpperCase());
  if (!m) return "info";
  const token = m[1];
  if (token === "CRITICAL" || token === "FATAL") return "critical";
  if (token === "ERROR") return "error";
  if (token === "WARNING" || token === "WARN") return "warning";
  if (token === "DEBUG" || token === "TRACE") return "debug";
  return "info";
}

function levelTone(level: Level) {
  return LEVEL_TONE[level];
}

/** Split a line into highlighted segments for the search term. */
function highlight(line: string, needle: string, isRegex: boolean, caseSensitive: boolean) {
  if (!needle) return [line];
  let parts: string[];
  try {
    const re = isRegex
      ? new RegExp(needle, caseSensitive ? "g" : "gi")
      : new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), caseSensitive ? "g" : "gi");
    parts = line.split(re);
  } catch {
    return [line];
  }
  if (parts.length === 1) return [line];
  const out: React.ReactNode[] = [];
  let cursor = 0;
  let idx = 0;
  const re = isRegex
    ? new RegExp(needle, caseSensitive ? "g" : "gi")
    : new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), caseSensitive ? "g" : "gi");
  re.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(line)) !== null) {
    if (match.index > cursor) out.push(line.slice(cursor, match.index));
    out.push(
      <mark key={idx++} style={{ background: "rgba(255,90,31,.28)", color: "#ffb59a", borderRadius: 2 }}>
        {match[0]}
      </mark>,
    );
    cursor = match.index + match[0].length;
    if (match[0].length === 0) re.lastIndex++;
  }
  if (cursor < line.length) out.push(line.slice(cursor));
  return out;
}

export default function Logs() {
  const index = useApi<{ files: LogFile[]; count: number; directory: string; categories: Record<string, number> }>(
    "/logs",
    { interval: 30000 },
  );
  const dash = useApi<DashboardPayload>("/logs/dashboard", { interval: 15000 });

  const [selected, setSelected] = useState<string | null>(null);
  const [log, setLog] = useState<LogContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [search, setSearch] = useState("");
  const [fileFilter, setFileFilter] = useState("");
  const [levelFilter, setLevelFilter] = useState<Level | "all">("all");
  const [useRegex, setUseRegex] = useState(false);
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [wrap, setWrap] = useState(true);
  const [sort, setSort] = useState<"modified" | "size" | "name">("modified");
  const [tail, setTail] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [compare, setCompare] = useState<string[]>([]);
  const [compareLog, setCompareLog] = useState<LogContent | null>(null);
  const [jump, setJump] = useState("");
  const viewerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (id: string) => {
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
  }, []);

  useEffect(() => {
    if (!selected && index.data?.files?.length) {
      void load(index.data.files[0].id);
    }
  }, [index.data, load, selected]);

  // Live tail: re-fetch the open file on an interval.
  useEffect(() => {
    if (!tail || !selected) return;
    const t = window.setInterval(() => {
      void api.get<LogContent>(`/logs/${selected}`).then((r) => setLog(r)).catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(t);
  }, [tail, selected]);

  // Compare mode loads the second file.
  useEffect(() => {
    const other = compare.find((id) => id !== selected);
    if (!other) {
      setCompareLog(null);
      return;
    }
    void api.get<LogContent>(`/logs/${other}`).then((r) => setCompareLog(r)).catch(() => setCompareLog(null));
  }, [compare, selected]);

  const files = index.data?.files ?? [];

  const filteredFiles = useMemo(() => {
    const q = fileFilter.trim().toLowerCase();
    let list = files.filter((f) => !q || f.id.toLowerCase().includes(q) || f.name.toLowerCase().includes(q));
    list = [...list].sort((a, b) => {
      if (sort === "size") return b.size - a.size;
      if (sort === "name") return a.id.localeCompare(b.id);
      return b.modified - a.modified;
    });
    return list;
  }, [files, fileFilter, sort]);

  const lines = useMemo(() => (log?.content ?? "").split("\n"), [log?.content]);

  const visibleLines = useMemo(() => {
    const needle = search.trim();
    return lines
      .map((text, i) => ({ n: i + 1, text, level: detectLevel(text) }))
      .filter((row) => {
        if (levelFilter !== "all" && row.level !== levelFilter) return false;
        if (!needle) return true;
        if (useRegex) {
          try {
            return new RegExp(needle, caseSensitive ? "" : "i").test(row.text);
          } catch {
            return true;
          }
        }
        const hay = caseSensitive ? row.text : row.text.toLowerCase();
        const ned = caseSensitive ? needle : needle.toLowerCase();
        return hay.includes(ned);
      });
  }, [lines, search, levelFilter, useRegex, caseSensitive]);

  const fileLevelCounts = useMemo(() => {
    const counts: Record<string, number> = { critical: 0, error: 0, warning: 0, info: 0, debug: 0 };
    for (const text of lines) counts[detectLevel(text)] += 1;
    return counts;
  }, [lines]);

  const totalBytes = files.reduce((a, f) => a + f.size, 0);

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

  const clear = async () => {
    if (!selected) return;
    try {
      await api.del(`/logs/${selected}`);
      setSelected(null);
      setLog(null);
      void index.refresh();
    } catch {
      /* ignore */
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

  const toggleCompare = (id: string) => {
    setCompare((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  };

  const gotoLine = () => {
    const n = Number(jump);
    if (!n || !viewerRef.current) return;
    const el = viewerRef.current.querySelector(`[data-line="${n}"]`);
    if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  const exportJson = () => {
    const payload = {
      file: log?.id ?? null,
      size: log?.size ?? 0,
      totalLines: log?.totalLines ?? 0,
      levels: fileLevelCounts,
      matches: visibleLines.length,
      generated: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(log?.id ?? "logs").replace(/[\\/]/g, "_")}-analysis.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const dashLevels = dash.data?.levels ?? {};
  const levelTotal = Object.values(dashLevels).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="page">
      <PageHeader
        title="Logs"
        subtitle="Full workspace log surface — file index, level analysis, regex search, live tail, side-by-side compare"
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={() => void index.refresh()}>
              <RefreshCw size={12} /> Refresh
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setTail((v) => !v)} aria-pressed={tail}>
              <Radio size={12} /> {tail ? "tail on" : "tail"}
            </Button>
            <Button size="sm" variant="ghost" onClick={exportJson} disabled={!log}>
              <Activity size={12} /> analyze
            </Button>
            <Button size="sm" variant="ghost" onClick={() => download("/api/logs/combined/download")}>
              <Download size={12} /> all
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={index.data?.count ?? "—"} label="Log files" tone="info" />
        <Stat value={formatBytes(totalBytes)} label="Total size" tone="info" />
        <Stat value={log?.totalLines ?? "—"} label="Lines in view" tone="ok" />
        <Stat value={visibleLines.length} label="Matching lines" tone="warn" />
      </div>

      <div className="split">
        <Panel
          title="Severity mix (all files)"
          actions={<span className="tiny mute">{levelTotal} classified</span>}
        >
          {levelTotal <= 1 ? (
            <Empty icon={<Activity size={16} />} title="No events yet" detail="Run a scan or command — output lands here." />
          ) : (
            <>
              <div style={{ display: "flex", height: 10, borderRadius: 999, overflow: "hidden", background: "var(--surface-3)" }}>
                {LEVELS.map((lv) => {
                  const v = dashLevels[lv] ?? 0;
                  if (!v) return null;
                  return <div key={lv} title={`${lv}: ${v}`} style={{ width: `${(v / levelTotal) * 100}%`, background: LEVEL_COLOR[lv] }} />;
                })}
              </div>
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 10 }}>
                {LEVELS.map((lv) => (
                  <button
                    key={lv}
                    className="tiny row"
                    style={{ gap: 6, background: "none", border: "none", color: "inherit", cursor: "pointer" }}
                    onClick={() => setLevelFilter(levelFilter === lv ? "all" : lv)}
                  >
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: LEVEL_COLOR[lv], display: "inline-block" }} />
                    <span className="mute">{lv}</span>
                    <strong className="mono">{dashLevels[lv] ?? 0}</strong>
                  </button>
                ))}
              </div>
            </>
          )}
        </Panel>

        <Panel
          title="Top event categories"
          actions={<span className="tiny mute">{Object.keys(dash.data?.categories ?? {}).length} distinct</span>}
        >
          {(dash.data?.topCategories ?? []).length === 0 ? (
            <Empty icon={<AlertTriangle size={16} />} title="No categories" detail="Categories appear once events are recorded." />
          ) : (
            (dash.data?.topCategories ?? []).slice(0, 8).map((c) => {
              const max = Math.max(...(dash.data?.topCategories ?? []).map((x) => x.count)) || 1;
              return (
                <div key={c.name} className="meter-row">
                  <div className="meter-label" style={{ width: 190 }}>{c.name}</div>
                  <div className="meter-track">
                    <div className="meter-fill" style={{ width: `${(c.count / max) * 100}%`, background: "var(--info)" }} />
                  </div>
                  <div className="meter-val">{c.count}</div>
                </div>
              );
            })
          )}
        </Panel>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: "300px 1fr", gap: 12, alignItems: "start" }}>
        <Panel
          title="Files"
          tight
          actions={
            <select className="input tiny" style={{ width: "auto", padding: "2px 6px" }} value={sort} onChange={(e) => setSort(e.target.value as any)}>
              <option value="modified">newest</option>
              <option value="size">largest</option>
              <option value="name">name</option>
            </select>
          }
        >
          <div style={{ padding: "6px 8px" }}>
            <input
              className="input mono tiny"
              style={{ width: "100%" }}
              placeholder="filter files…"
              value={fileFilter}
              onChange={(e) => setFileFilter(e.target.value)}
            />
          </div>
          <div style={{ maxHeight: 520, overflowY: "auto" }}>
            {index.loading && !index.data ? (
              <div style={{ padding: 16 }}><Loader2 size={14} className="animate-spin" /></div>
            ) : filteredFiles.length === 0 ? (
              <Empty icon={<FileText size={16} />} title="No logs yet" detail="Run a scan or command — output lands here." />
            ) : (
              filteredFiles.map((f) => (
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
                    <div className="tiny mute td-truncate" title={f.dir}>{f.dir.replace(/^C:.*\.pegasus/, "~/.pegasus")}</div>
                    <div className="row tiny" style={{ gap: 4, marginTop: 3 }}>
                      {LEVELS.map((lv) => {
                        const n = dashLevels[lv] ?? 0;
                        if (!n) return null;
                        return <span key={lv} title={`${lv}: ${n}`} style={{ width: 6, height: 6, borderRadius: 999, background: LEVEL_COLOR[lv], display: "inline-block" }} />;
                      })}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="tiny mute">{formatBytes(f.size)}</div>
                    <div className="tiny mute">{timeAgo(f.modified)}</div>
                  </div>
                  <button
                    className="btn btn-xs"
                    title="Add to compare"
                    onClick={(e) => { e.stopPropagation(); toggleCompare(f.id); }}
                    style={{ color: compare.includes(f.id) ? "var(--signal)" : undefined }}
                  >
                    <GitCompare size={11} />
                  </button>
                </div>
              ))
            )}
          </div>
        </Panel>

        <div>
          <Panel
            title={selected ?? "Viewer"}
            tight
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
                <Button size="sm" variant="ghost" onClick={clear} disabled={!selected} title="Delete selected log">
                  <Trash2 size={12} /> delete
                </Button>
              </>
            }
          >
            <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--line)", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 260px" }}>
                <Field label={useRegex ? "Search (regex)" : "Search"}>
                  <input
                    className="input mono tiny"
                    placeholder={useRegex ? "ERROR|FATAL|timeout" : "substring…"}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </Field>
              </div>
              <div className="row" style={{ gap: 6 }}>
                <button
                  className={`btn btn-xs ${useRegex ? "btn-primary" : ""}`}
                  onClick={() => setUseRegex((v) => !v)}
                  title="Regular expression search"
                >
                  <Filter size={11} /> .*
                </button>
                <button
                  className={`btn btn-xs ${caseSensitive ? "btn-primary" : ""}`}
                  onClick={() => setCaseSensitive((v) => !v)}
                  title="Case sensitive"
                >
                  Aa
                </button>
                <button
                  className={`btn btn-xs ${wrap ? "btn-primary" : ""}`}
                  onClick={() => setWrap((v) => !v)}
                  title="Wrap long lines"
                >
                  ⇄
                </button>
              </div>
              <div style={{ width: 120 }}>
                <Field label="Jump to line">
                  <div className="row" style={{ gap: 4 }}>
                    <input className="input mono tiny" value={jump} onChange={(e) => setJump(e.target.value)} placeholder="1234" />
                    <button className="btn btn-xs" onClick={gotoLine} title="Scroll to line">↵</button>
                  </div>
                </Field>
              </div>
            </div>

            <div style={{ padding: "6px 12px", borderBottom: "1px solid var(--line)", display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button className={`btn btn-xs ${levelFilter === "all" ? "btn-primary" : ""}`} onClick={() => setLevelFilter("all")}>all</button>
              {LEVELS.map((lv) => (
                <button
                  key={lv}
                  className={`btn btn-xs ${levelFilter === lv ? "btn-primary" : ""}`}
                  onClick={() => setLevelFilter(levelFilter === lv ? "all" : lv)}
                >
                  <span style={{ width: 6, height: 6, borderRadius: 999, background: LEVEL_COLOR[lv], display: "inline-block" }} />
                  {lv}
                </button>
              ))}
              {log && (
                <span className="tiny mute" style={{ marginLeft: "auto", alignSelf: "center" }}>
                  {visibleLines.length} / {lines.length} shown
                </span>
              )}
            </div>

            {editMode ? (
              <div style={{ padding: 10 }}>
                <textarea
                  className="input mono tiny"
                  style={{ width: "100%", height: 440, background: "#0d1117", color: "#c9d1d9", border: "1px solid #30363d", borderRadius: 6, padding: 10 }}
                  value={editedContent}
                  onChange={(e) => setEditedContent(e.target.value)}
                  spellCheck={false}
                />
                <div style={{ paddingTop: 6, display: "flex", gap: 6 }}>
                  <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(editedContent).catch(() => {}); }}>
                    <Copy size={12} /> copy
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditMode(false)}>close</Button>
                </div>
              </div>
            ) : loading ? (
              <div style={{ padding: 24, textAlign: "center" }}><Loader2 size={16} className="animate-spin" /></div>
            ) : error ? (
              <Empty icon={<FileText size={16} />} title="Could not read log" detail={error} action={<Button size="sm" onClick={() => selected && void load(selected)}>Retry</Button>} />
            ) : !log ? (
              <Empty icon={<FileText size={16} />} title="Select a file" detail="Pick a log on the left to view it." />
            ) : visibleLines.length === 0 ? (
              <Empty icon={<Search size={16} />} title="No matching lines" detail="Adjust the search or level filter." />
            ) : (
              <div
                ref={viewerRef}
                style={{
                  maxHeight: 460,
                  overflow: "auto",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11.5,
                  lineHeight: 1.55,
                  padding: "8px 0",
                }}
              >
                {visibleLines.slice(0, 3000).map((row) => (
                  <div
                    key={row.n}
                    data-line={row.n}
                    style={{
                      display: "flex",
                      gap: 10,
                      padding: "0 12px",
                      whiteSpace: wrap ? "pre-wrap" : "pre",
                      borderLeft: row.level === "critical" || row.level === "error" ? "2px solid rgba(248,81,73,.55)" : "2px solid transparent",
                    }}
                  >
                    <span style={{ color: "var(--ink-mute)", minWidth: 52, textAlign: "right", userSelect: "none" }}>{row.n}</span>
                    <span style={{ color: LEVEL_COLOR[row.level] }}>{highlight(row.text, search, useRegex, caseSensitive)}</span>
                  </div>
                ))}
                {visibleLines.length > 3000 && (
                  <div className="tiny mute" style={{ padding: "8px 12px" }}>
                    … {visibleLines.length - 3000} more lines not rendered — refine the search or download the file.
                  </div>
                )}
              </div>
            )}
          </Panel>

          {compare.length > 0 && (
            <Panel
              title={`Compare${compareLog ? ` — ${compareLog.id} vs ${selected}` : ""}`}
              actions={<Button size="sm" variant="ghost" onClick={() => setCompare([])}><X size={12} /> clear</Button>}
              tight
            >
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>Metric</th><th>{selected ?? "—"}</th><th>{compareLog?.id ?? "…"}</th></tr></thead>
                  <tbody>
                    <tr>
                      <td>Lines</td>
                      <td className="mono tiny">{log?.totalLines ?? "—"}</td>
                      <td className="mono tiny">{compareLog?.totalLines ?? "—"}</td>
                    </tr>
                    <tr>
                      <td>Size</td>
                      <td className="mono tiny">{log ? formatBytes(log.size) : "—"}</td>
                      <td className="mono tiny">{compareLog ? formatBytes(compareLog.size) : "—"}</td>
                    </tr>
                    <tr>
                      <td>Modified</td>
                      <td className="tiny">{log ? formatDateTime(log.modified) : "—"}</td>
                      <td className="tiny">{compareLog ? formatDateTime(compareLog.modified) : "—"}</td>
                    </tr>
                    <tr>
                      <td>Level mix</td>
                      <td className="mono tiny">
                        {LEVELS.map((lv) => `${lv}:${fileLevelCounts[lv] ?? 0}`).join(" ")}
                      </td>
                      <td className="mono tiny">
                        {compareLog
                          ? LEVELS.map((lv) => `${lv}:${compareLog.content.split("\n").filter((l) => detectLevel(l) === lv).length}`).join(" ")
                          : "—"}
                      </td>
                    </tr>
                    <tr>
                      <td>First line</td>
                      <td className="tiny mono td-truncate">{lines[0]?.slice(0, 90) ?? "—"}</td>
                      <td className="tiny mono td-truncate">{compareLog?.content.split("\n")[0]?.slice(0, 90) ?? "—"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          <Panel
            title="Event timeline"
            actions={
              <Button size="sm" variant="ghost" onClick={() => setEditMode((v) => !v)} disabled={!log}>
                <FileText size={12} /> {editMode ? "view" : "edit"}
              </Button>
            }
            tight
          >
            {(dash.data?.timeline ?? []).length === 0 ? (
              <Empty icon={<Activity size={16} />} title="No events" detail="Events recorded by the platform appear here." />
            ) : (
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>When</th><th>Level</th><th>Event</th><th>Status</th><th>Detail</th></tr></thead>
                  <tbody>
                    {(dash.data?.timeline ?? []).slice(0, 60).map((row, i) => (
                      <tr key={`${row.ts}-${i}`}>
                        <td className="mono tiny">{row.ts ? formatDateTime(Date.parse(row.ts) || 0) : "—"}</td>
                        <td><Badge tone={levelTone(detectLevel(row.note || row.status))}>{detectLevel(row.note || row.status)}</Badge></td>
                        <td className="td-strong td-truncate">{row.event}</td>
                        <td className="tiny mono">{row.status || "—"}</td>
                        <td className="tiny mute td-truncate">{row.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className="split">
        <Panel title="File-level level counts" tight>
          {selected && log ? (
            LEVELS.map((lv) => (
              <div key={lv} className="meter-row">
                <div className="meter-label" style={{ width: 90 }}>{lv}</div>
                <div className="meter-track">
                  <div className="meter-fill" style={{ width: `${Math.min(100, (fileLevelCounts[lv] ?? 0) * 2)}%`, background: LEVEL_COLOR[lv] }} />
                </div>
                <div className="meter-val">{fileLevelCounts[lv] ?? 0}</div>
              </div>
            ))
          ) : (
            <Empty icon={<ChevronRight size={16} />} title="No file selected" detail="Select a file to analyse its level mix." />
          )}
        </Panel>

        <Panel title="Source" tight>
          <div className="tiny" style={{ lineHeight: 1.9 }}>
            <div><span className="mute">log directory</span><br /><code className="td-truncate">{index.data?.directory ?? "—"}</code></div>
            <div style={{ marginTop: 8 }}><span className="mute">events file</span><br /><code className="td-truncate">{dash.data?.eventsFile || "—"}</code></div>
            <div style={{ marginTop: 8 }}><span className="mute">total size</span><br /><strong className="mono">{formatBytes(totalBytes)}</strong></div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
