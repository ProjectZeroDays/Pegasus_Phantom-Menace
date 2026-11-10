import { useState } from "react";
import { Globe, Play, RefreshCw, Square } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, Field, Input, PageHeader, Panel, Stat } from "@/components/ui";

interface Tunnel {
  id: string;
  installed: boolean;
  binary: string;
  running: boolean;
  pids: number[];
  public_url: string | null;
  port: number | null;
  started: number | null;
}

export default function Tunnels() {
  const status = useApi<{ providers: Tunnel[] }>("/tunnels/status", { interval: 10000 });
  const [port, setPort] = useState("5095");
  const [msg, setMsg] = useState<string | null>(null);

  const start = async (id: string) => {
    setMsg(null);
    try {
      const res = await api.post<{ public_url: string | null }>(`/tunnels/${id}/start`, {
        port: Number(port) || 5095,
      });
      setMsg(`${id} started${res.public_url ? ` at ${res.public_url}` : ""}`);
      status.refresh();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not start tunnel");
    }
  };

  const stop = async (id: string) => {
    await api.post(`/tunnels/${id}/stop`);
    setMsg(`${id} stopped`);
    status.refresh();
  };

  return (
    <div className="page">
      <PageHeader title="Public Tunnels" subtitle="ngrok and cloudflared exposure for the console."
        actions={<Button size="sm" onClick={status.refresh}><RefreshCw size={12} /> Refresh</Button>} />

      <div className="stat-grid">
        <Stat value={(status.data?.providers ?? []).filter((p) => p.running).length} label="Running" tone="ok" />
        <Stat value={(status.data?.providers ?? []).length} label="Providers" tone="info" />
        <Stat value={port} label="Local port" tone="warn" />
      </div>

      <Panel title="Local port">
        <Field label="Port the console listens on">
          <Input value={port} onChange={setPort} placeholder="5095" />
        </Field>
      </Panel>

      <Panel title="Providers">
        <div className="stack">
          {(status.data?.providers ?? []).map((p) => (
            <div key={p.id} className="vault-item">
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="mono" style={{ fontSize: 12 }}>{p.id}</span>
                    <Badge tone={p.installed ? (p.running ? "ok" : "warn") : "dim"}>
                      {p.installed ? (p.running ? "running" : "installed") : "not installed"}
                    </Badge>
                  </div>
                  <div className="tiny mute">
                    {p.binary || "binary not found on PATH"}
                    {p.public_url ? ` \u00b7 ${p.public_url}` : ""}
                  </div>
                </div>
                <div className="row" style={{ gap: 6 }}>
                  <Button size="xs" variant="primary" disabled={!p.installed || p.running}
                    onClick={() => void start(p.id)}>
                    <Play size={11} /> Start
                  </Button>
                  <Button size="xs" variant="danger" disabled={!p.running}
                    onClick={() => void stop(p.id)}>
                    <Square size={11} /> Stop
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
        {msg ? <div className="mono tiny" style={{ marginTop: 8 }}>{msg}</div> : null}
        <div className="tiny mute" style={{ marginTop: 8 }}>
          <Globe size={10} /> Public exposure is a decision for the operator. Use a tunnel only
          when the engagement requires it.
        </div>
      </Panel>
    </div>
  );
}
