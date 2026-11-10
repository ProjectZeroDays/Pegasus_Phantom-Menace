import { useState } from "react";
import { Bug, RefreshCw, Send, Star } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, Input, PageHeader, Panel, Select, Stat, Textarea } from "@/components/ui";

interface Report {
  id: string;
  title: string;
  description: string;
  severity: string;
  component: string;
  reporter: string;
  created: number;
  status: string;
}

export default function BugReport() {
  const reports = useApi<{ reports: Report[] }>("/bug-reports", { interval: 30000 });
  const repo = useApi<{ repository: string; stars: number | null; forks: number | null; open_issues: number | null }>(
    "/stars/repository",
    { interval: 60000 },
  );
  const stars = useApi<{ stars: { key: string; created: number }[] }>("/stars", { interval: 30000 });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("normal");
  const [component, setComponent] = useState("console");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const submit = async () => {
    if (!title.trim()) {
      setMsg("a title is required");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await api.post("/bug-reports", {
        title: title.trim(),
        description,
        severity,
        component,
      });
      setTitle("");
      setDescription("");
      reports.refresh();
      setMsg("report filed");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not file report");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <PageHeader title="Bug Reports" subtitle="File an issue and follow the repository."
        actions={<Button size="sm" onClick={reports.refresh}><RefreshCw size={12} /> Refresh</Button>} />

      <div className="stat-grid">
        <Stat value={reports.data?.reports.length ?? 0} label="Filed" tone="info" />
        <Stat value={repo.data?.stars ?? "—"} label="Repo stars" tone="warn" />
        <Stat value={stars.data?.stars.length ?? 0} label="Starred items" tone="ok" />
      </div>

      <Panel title="File a report">
        <Field label="Title">
          <Input value={title} onChange={setTitle} placeholder="what went wrong" />
        </Field>
        <div className="grid-2" style={{ gap: 10, marginTop: 8 }}>
          <div className="col">
            <Field label="Severity">
              <Select value={severity} onChange={setSeverity}>
                {["low", "normal", "high", "critical"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </Field>
          </div>
          <div className="col">
            <Field label="Component">
              <Select value={component} onChange={setComponent}>
                {["console", "backend", "desktop", "plugins", "agents", "docs"].map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
        <div style={{ marginTop: 8 }}>
          <Field label="Description">
            <Textarea value={description} onChange={setDescription} rows={5} placeholder="steps, logs, expectation" />
          </Field>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <Button variant="primary" onClick={() => void submit()} disabled={busy}>
            <Send size={13} /> {busy ? "filing…" : "File report"}
          </Button>
          {msg ? <span className="mono tiny">{msg}</span> : null}
        </div>
      </Panel>

      <Panel title="Filed reports">
        {(reports.data?.reports ?? []).length === 0 ? (
          <Empty icon={<Bug size={22} />} title="No reports filed" />
        ) : (
          <div className="stack">
            {(reports.data?.reports ?? []).map((r) => (
              <div key={r.id} className="vault-item">
                <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div className="mono" style={{ fontSize: 12 }}>{r.title}</div>
                    <div className="tiny mute">{r.component} &middot; {r.severity} &middot; {r.status}</div>
                  </div>
                  <Badge tone={r.severity === "critical" ? "err" : "dim"}>{r.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Starred items">
        {(stars.data?.stars ?? []).length === 0 ? (
          <Empty icon={<Star size={22} />} title="Nothing starred" />
        ) : (
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
            {(stars.data?.stars ?? []).map((s) => (
              <Badge key={s.key} tone="warn"><Star size={10} /> {s.key}</Badge>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
