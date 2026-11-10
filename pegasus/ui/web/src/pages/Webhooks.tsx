import { useState } from "react";
import { CheckCircle2, Link2, Plus, RefreshCw, Send, Trash2, Webhook } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface WebhookEntry {
  id: string;
  url: string;
  events: string[];
  secret: string;
  active: boolean;
  created_at: number;
  max_retries: number;
  timeout: number;
}

interface WebhookEvent {
  target: string;
  event: string;
  ts: number;
  status: number;
  delivered: boolean;
  error?: string;
}

export default function Webhooks() {
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [events, setEvents] = useState("pegasus.test,job.completed,alert");
  const [busy, setBusy] = useState(false);

  const list = useApi<{ webhooks: WebhookEntry[] }>("/webhooks", { interval: 15000 });
  const log = useApi<{ events: WebhookEvent[] }>("/webhooks/events", { interval: 15000 });

  const hooks = list.data?.webhooks ?? [];
  const entries = log.data?.events ?? [];

  const create = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api.post("/webhooks", { url: url.trim(), events: events.split(",").map((s) => s.trim()).filter(Boolean), secret: secret || undefined });
      setUrl("");
      setSecret("");
      list.refresh();
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.del(`/webhooks/${id}`);
    list.refresh();
  };

  const test = async (hook: WebhookEntry) => {
    await api.post("/webhooks/test", { id: hook.id });
    log.refresh();
  };

  const delivered = entries.filter((e) => e.delivered).length;

  return (
    <div className="page">
      <PageHeader
        title="Webhooks"
        subtitle="Real-time external integrations with HMAC-SHA256 signed delivery"
        actions={<Button size="sm" onClick={() => { list.refresh(); log.refresh(); }}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={hooks.length} label="Registered webhooks" tone="info" />
        <Stat value={hooks.filter((h) => h.active).length} label="Active" tone="ok" />
        <Stat value={entries.length} label="Test deliveries" tone="warn" />
        <Stat value={delivered} label="Delivered OK" tone="ok" />
      </div>

      <Panel title="Register endpoint">
        <div className="form-row">
          <Field label="Target URL">
            <input className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hook" />
          </Field>
          <Field label="Events (comma separated)">
            <input className="input" value={events} onChange={(e) => setEvents(e.target.value)} placeholder="job.completed,alert" />
          </Field>
          <Field label="Secret (optional)">
            <input className="input" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="HMAC signing key" type="password" />
          </Field>
          <Field label="Add">
            <button className="btn btn-primary" onClick={() => void create()} disabled={busy || !url.trim()}>
              <Plus size={13} /> Register
            </button>
          </Field>
        </div>
        <p className="tiny mute">Signature header: <code>X-Pegasus-Signature</code> = hex(HMAC-SHA256(secret, raw_body)). Deliveries are operator-triggered only (Test); nothing fires automatically.</p>
      </Panel>

      <Panel title="Endpoints" tight>
        {hooks.length === 0 ? (
          <Empty icon={<Webhook size={16} />} title="No webhooks registered" detail="Register an endpoint above to receive signed event deliveries." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>URL</th><th>Events</th><th>Signed</th><th /></tr></thead>
              <tbody>
                {hooks.map((hook) => (
                  <tr key={hook.id}>
                    <td className="td-strong td-truncate"><Link2 size={11} style={{ display: "inline", marginRight: 4 }} />{hook.url}</td>
                    <td className="tiny mono">{hook.events.join(", ")}</td>
                    <td>{hook.secret ? <Badge tone="primary">HMAC</Badge> : <Badge tone="dim">unsigned</Badge>}</td>
                    <td>
                      <button className="btn btn-xs btn-primary" onClick={() => void test(hook)} title="Send signed test delivery">
                        <Send size={11} /> test
                      </button>{" "}
                      <button className="btn btn-xs" onClick={() => void remove(hook.id)} title="Remove endpoint">
                        <Trash2 size={11} /> delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Recent deliveries" tight>
        {entries.length === 0 ? (
          <Empty icon={<CheckCircle2 size={16} />} title="No deliveries yet" detail="Press Test on an endpoint to fire a signed delivery." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Target</th><th>Result</th><th>Status</th><th>When</th></tr></thead>
              <tbody>
                {entries.slice(-25).reverse().map((entry, i) => (
                  <tr key={`${entry.ts}-${i}`}>
                    <td className="mono tiny td-truncate">{entry.target}</td>
                    <td>{entry.delivered ? <Badge tone="ok">delivered</Badge> : <Badge tone="err">{entry.error ? "error" : "failed"}</Badge>}</td>
                    <td className="mono tiny">{entry.status || "—"}</td>
                    <td className="tiny mute">{new Date(entry.ts * 1000).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
