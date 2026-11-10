import { useState } from "react";
import { Cloud, Play, RefreshCw, Square, Zap } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface RelayStatus {
  active: boolean;
  tunnel: string | null;
  port?: number | null;
}

export default function RelayDashboard() {
  const [port, setPort] = useState("5001");
  const [busy, setBusy] = useState(false);
  const status = useApi<RelayStatus>("/relay/status", { interval: 10000 });

  const active = status.data?.active ?? false;
  const url = status.data?.tunnel ?? null;

  const toggle = async () => {
    setBusy(true);
    try {
      if (active) {
        await api.del("/relay");
      } else {
        await api.post("/relay/start", { port: Number(port) || 5001 });
      }
      setTimeout(() => status.refresh(), 1500);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Cloud Relay"
        subtitle="Encrypted relay tunnel for remote C2 operations and command forwarding"
        actions={<Button size="sm" onClick={status.refresh}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={active ? "LIVE" : "IDLE"} label="Relay tunnel" tone={active ? "ok" : "info"} />
        <Stat value={port} label="Local port" tone="info" />
        <Stat value={url ? "reachable" : "—"} label="Public endpoint" tone={url ? "ok" : "info"} />
      </div>

      <Panel title="Tunnel control">
        <div className="form-row">
          <Field label="Local service port">
            <input className="input" value={port} onChange={(e) => setPort(e.target.value)} inputMode="numeric" disabled={active} />
          </Field>
          <Field label="Relay">
            <button className={`btn ${active ? "btn-danger" : "btn-primary"}`} onClick={() => void toggle()} disabled={busy}>
              {active ? <><Square size={13} /> Stop relay</> : <><Play size={13} /> Start relay</>}
            </button>
          </Field>
        </div>
        <p className="tiny mute">The relay bridges the local web backend to a publicly reachable endpoint for remote operator access during authorized engagements. Requires a tunnel binary (e.g. ngrok/cloudflared) on PATH; if missing the API returns 503 and nothing is exposed.</p>
      </Panel>

      <Panel title="Public endpoint" tight>
        {url ? (
          <div className="mono" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <Badge tone="ok">LIVE</Badge>
            <a href={url} target="_blank" rel="noreferrer" className="link">{url}</a>
            <button className="btn btn-xs" onClick={() => void navigator.clipboard?.writeText(url)}><Cloud size={11} /> copy</button>
          </div>
        ) : (
          <Empty icon={<Zap size={16} />} title="Relay not running" detail="Start the relay to receive a public endpoint. If a tunnel binary is missing you'll get a 503 with a clear error." />
        )}
      </Panel>

      <Panel title="Operational guidance" tight>
        <ul className="tiny" style={{ margin: 0, paddingLeft: 18 }}>
          <li>Every relayed session is attributable: rotate secrets between engagements.</li>
          <li>Stop the relay when the engagement ends; it terminates the public endpoint.</li>
          <li>Pair with the C2 Dashboard for beacon/listener state and Post-Exploitation for data channels.</li>
        </ul>
      </Panel>
    </div>
  );
}
