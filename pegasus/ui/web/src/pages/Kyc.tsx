import { useState } from "react";
import { ExternalLink, IdCard, RefreshCw } from "lucide-react";
import { api, ApiError, useApi } from "@/lib/api";
import { Badge, Button, PageHeader, Panel, Select, Stat } from "@/components/ui";

interface Provider {
  id: string;
  name: string;
  url: string;
  stage: string;
  status: string;
}

interface KycState {
  provider?: string;
  status?: string;
  started?: number;
  webview_url?: string;
}

export default function Kyc() {
  const providers = useApi<{ providers: Provider[] }>("/kyc/providers", { interval: 30000 });
  const state = useApi<{ kyc: KycState }>("/kyc/status", { interval: 30000 });
  const [provider, setProvider] = useState("persona");
  const [status, setStatus] = useState("in progress");
  const [msg, setMsg] = useState<string | null>(null);

  const start = async () => {
    try {
      await api.post("/kyc/start", { provider });
      state.refresh();
      providers.refresh();
      setMsg("KYC engagement opened");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "could not start KYC");
    }
  };

  const setStatusNow = async () => {
    await api.post("/kyc/status", { status });
    state.refresh();
    providers.refresh();
  };

  return (
    <div className="page">
      <PageHeader title="KYC Onboarding" subtitle="Compliance provider onboarding for the organisation."
        actions={<Button size="sm" onClick={() => { state.refresh(); providers.refresh(); }}>
          <RefreshCw size={12} /> Refresh
        </Button>} />

      <div className="stat-grid">
        <Stat value={state.data?.kyc?.status ?? "not started"} label="Status" tone="warn" />
        <Stat value={(providers.data?.providers ?? []).length} label="Providers" tone="info" />
        <Stat value="manual" label="Verification" tone="ok" />
      </div>

      <Panel title="Providers">
        <div className="row" style={{ gap: 8 }}>
          <Select value={provider} onChange={setProvider}>
            {(providers.data?.providers ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </Select>
          <Button variant="primary" onClick={() => void start()}>
            <IdCard size={13} /> Open onboarding
          </Button>
        </div>
        <div className="stack" style={{ marginTop: 10 }}>
          {(providers.data?.providers ?? []).map((p) => (
            <div key={p.id} className="vault-item">
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className="mono" style={{ fontSize: 12 }}>{p.name}</span>
                    <Badge tone={p.status === "approved" ? "ok" : "dim"}>{p.status}</Badge>
                  </div>
                  <div className="tiny mute">{p.stage}</div>
                </div>
                <a href={p.url} target="_blank" rel="noreferrer" className="mono tiny">
                  <ExternalLink size={11} /> open
                </a>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Record progress">
        <div className="row" style={{ gap: 8 }}>
          <Select value={status} onChange={setStatus}>
            {["not started", "in progress", "submitted", "approved", "rejected", "needs review"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
          <Button size="sm" onClick={() => void setStatusNow()}>Update</Button>
        </div>
        {msg ? <div className="mono tiny" style={{ marginTop: 8 }}>{msg}</div> : null}
        <div className="tiny mute" style={{ marginTop: 8 }}>
          Verification is completed by the provider. The console records the engagement
          state only and never automates or bypasses identity checks.
        </div>
      </Panel>
    </div>
  );
}
