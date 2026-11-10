import { useState } from "react";
import { Download, Globe, Lock, RefreshCw, ShieldCheck } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, PageHeader, Panel, Stat } from "@/components/ui";

interface Provider {
  id: string;
  name: string;
  purpose: string;
  installed: boolean;
  binary: string;
  detail: string;
  version: string | null;
}

interface Status {
  providers: Provider[];
  auto_update: boolean;
  last_update_check: number;
  bin_dir: string;
}

export default function Privacy() {
  const status = useApi<Status>("/privacy/status", { interval: 15000 });
  const [msg, setMsg] = useState<string | null>(null);

  const install = async (id: string) => {
    setMsg(null);
    try {
      const res = await api.post<Record<string, unknown>>(`/privacy/install/${id}`, {});
      setMsg(`${id}: ${JSON.stringify(res).slice(0, 160)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const body = e.body as { plan?: { url?: string } } | null;
        const url = body?.plan?.url;
        if (!url) {
          setMsg(`${id}: nothing to download`);
          return;
        }
        if (!window.confirm(`Download ${id} from ${url}?`)) return;
        try {
          await api.post(`/privacy/install/${id}`, { confirm: true, url });
          setMsg(`${id}: installed`);
          status.refresh();
        } catch (inner) {
          setMsg(inner instanceof ApiError ? inner.message : "install failed");
        }
        return;
      }
      setMsg(e instanceof ApiError ? e.message : "install failed");
    }
  };

  const toggleAuto = async () => {
    const next = !status.data?.auto_update;
    await api.post("/privacy/auto-update", { enabled: next });
    status.refresh();
  };

  return (
    <div className="page">
      <PageHeader title="Privacy Tooling" subtitle="No-IP, DNSCrypt, Tor, Onion and SOCKS5 management."
        actions={
          <div className="row" style={{ gap: 8 }}>
            <Button size="sm" onClick={() => void api.post("/privacy/check-updates").then(status.refresh)}>
              <RefreshCw size={12} /> Check updates
            </Button>
            <Button size="sm" variant={status.data?.auto_update ? "primary" : "default"} onClick={() => void toggleAuto()}>
              <ShieldCheck size={12} /> Auto-update {status.data?.auto_update ? "on" : "off"}
            </Button>
          </div>
        } />

      <div className="stat-grid">
        <Stat value={(status.data?.providers ?? []).filter((p) => p.installed).length} label="Installed" tone="ok" />
        <Stat value={(status.data?.providers ?? []).length} label="Providers" tone="info" />
        <Stat value={status.data?.auto_update ? "on" : "off"} label="Auto-update" tone="warn" />
      </div>

      <Panel title="Providers">
        <div className="stack">
          {(status.data?.providers ?? []).map((p) => (
            <div key={p.id} className="vault-item">
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="mono" style={{ fontSize: 12 }}>{p.name}</span>
                    <Badge tone={p.installed ? "ok" : "dim"}>{p.installed ? "installed" : "not installed"}</Badge>
                  </div>
                  <div className="tiny mute">{p.purpose} &middot; {p.detail}</div>
                </div>
                <Button size="xs" onClick={() => void install(p.id)}>
                  <Download size={11} /> Install
                </Button>
              </div>
            </div>
          ))}
        </div>
        {msg ? <div className="mono tiny" style={{ marginTop: 8 }}>{msg}</div> : null}
        <div className="tiny mute" style={{ marginTop: 8 }}>
          <Lock size={10} /> Binaries are stored in {status.data?.bin_dir ?? "~/.pegasus/bin"}.
          Service registration always requires explicit confirmation.
        </div>
      </Panel>

      <Panel title="Onion &amp; proxy endpoints">
        <div className="row" style={{ gap: 8 }}>
          <Badge tone="dim"><Globe size={10} /> onion via Tor SOCKS 127.0.0.1:9050</Badge>
        </div>
      </Panel>
    </div>
  );
}
