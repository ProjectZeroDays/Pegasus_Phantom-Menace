import { useEffect, useState } from "react";
import { KeyRound, Cpu, ArrowRight, Check, Loader2 } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Panel } from "@/components/ui";

interface ProviderMeta {
  id: string;
  label: string;
  env: string | null;
  kind: string;
}

interface SetupState {
  needsSetup: boolean;
  providers: ProviderMeta[];
  configured: string[];
  default: string | null;
  fallback: string | null;
  localModel: string | null;
  platform: string;
}

interface ModelRec {
  id: string;
  downloads: number;
  files: string[];
  tier: string;
  est_gb: number;
  fits: boolean;
}

export default function Setup() {
  const state = useApi<SetupState>("/setup/state");
  const models = useApi<{ models: ModelRec[]; platform: string }>("/models/recommended");
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [default_, setDefault] = useState<string>("");
  const [fallback, setFallback] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (state.data?.default) setDefault(state.data.default);
    if (state.data?.fallback) setFallback(state.data.fallback);
  }, [state.data?.default, state.data?.fallback]);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.post("/setup/providers", { keys, default: default_ || undefined, fallback: fallback || undefined });
      setDone(true);
      window.setTimeout(() => { window.location.href = "/"; }, 900);
    } catch (e: any) {
      setErr(e?.message ?? "failed");
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    setBusy(true);
    try {
      await api.post("/setup/skip");
      setDone(true);
      window.setTimeout(() => { window.location.href = "/"; }, 900);
    } catch (e: any) {
      setErr(e?.message ?? "failed");
    } finally {
      setBusy(false);
    }
  };

  const downloadModel = async (m: ModelRec) => {
    setDownloading(m.id);
    try {
      await api.post("/models/download", { model: m.id, filename: m.files[0] });
      await api.post("/models/select", { model: m.id, filename: m.files[0] });
      setDefault("local");
    } catch (e: any) {
      setErr(e?.message ?? "download failed");
    } finally {
      setDownloading(null);
    }
  };

  const cloud = (state.data?.providers ?? []).filter((p) => p.kind === "cloud");

  const [toolResults, setToolResults] = useState<{ key: string; status: string; detail?: string }[] | null>(null);
  const [installing, setInstalling] = useState(false);
  const installTools = async () => {
    setInstalling(true);
    try {
      const r = await api.post<{ results: { key: string; status: string; detail?: string }[] }>("/tools/install", {});
      setToolResults(r.results ?? []);
    } catch (e: any) {
      setErr(e?.message ?? "install failed");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", padding: "0 20px" }}>
      <div className="mono" style={{ fontSize: 13, letterSpacing: ".12em", color: "#ff9e00", marginBottom: 4 }}>
        PEGASUS PHANTOM MENACE
      </div>
      <h1 style={{ color: "#fff", fontSize: 26, margin: "0 0 4px" }}>Setup</h1>
      <p className="tiny mute" style={{ marginBottom: 24 }}>
        Add at least one provider API key, or pick a local model that fits this machine.
      </p>

      {done && (
        <div className="panel" style={{ padding: 14, marginBottom: 16, border: "1px solid #2ea043" }}>
          <span className="mono tiny" style={{ color: "#3fb950" }}>✓ configured — redirecting…</span>
        </div>
      )}

      <Panel title="Provider keys" actions={<Badge tone={state.data?.configured?.length ? "ok" : "warn"}>{state.data?.configured?.length ?? 0} set</Badge>}>
        <div style={{ display: "grid", gap: 10 }}>
          {cloud.map((p) => (
            <div key={p.id} className="row" style={{ gap: 8, alignItems: "center" }}>
              <label className="mono tiny" style={{ width: 110 }}>{p.label}</label>
              <input
                type="password"
                className="mono tiny"
                style={{ flex: 1, padding: 7, borderRadius: 6, border: "1px solid rgba(255,255,255,.08)", background: "#0d1117", color: "#e6edf3" }}
                placeholder={state.data?.configured?.includes(p.id) ? "configured ✓" : "sk-…"}
                value={keys[p.id] ?? ""}
                onChange={(e) => setKeys({ ...keys, [p.id]: e.target.value })}
              />
              {state.data?.configured?.includes(p.id) && <Check size={13} className="text-green-400" />}
            </div>
          ))}
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <label className="mono tiny" style={{ width: 110 }}>Default</label>
            <select className="mono tiny" style={{ padding: 7, flex: 1, background: "#0d1117", color: "#e6edf3", borderRadius: 6, border: "1px solid rgba(255,255,255,.08)" }}
              value={default_} onChange={(e) => setDefault(e.target.value)}>
              <option value="">—</option>
              {cloud.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              <option value="local">Local model</option>
            </select>
          </div>
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <label className="mono tiny" style={{ width: 110 }}>Fallback</label>
            <select className="mono tiny" style={{ padding: 7, flex: 1, background: "#0d1117", color: "#e6edf3", borderRadius: 6, border: "1px solid rgba(255,255,255,.08)" }}
              value={fallback} onChange={(e) => setFallback(e.target.value)}>
              <option value="">—</option>
              {cloud.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              <option value="local">Local model</option>
            </select>
          </div>
        </div>
      </Panel>

      <Panel title={`Local model — ${models.data?.platform ?? "gguf"} tier`} actions={<Badge tone="info">{models.data?.models?.length ?? 0} fit</Badge>}>
        <p className="tiny mute" style={{ margin: "0 0 10px" }}>
          Abliterated, quantized, ranked by what fits this machine's RAM. GGUF on Windows/Linux/Android, MLX on Apple silicon.
        </p>
        <div style={{ display: "grid", gap: 8 }}>
          {(models.data?.models ?? []).slice(0, 6).map((m) => (
            <div key={m.id} className="row" style={{ gap: 8, alignItems: "center" }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="mono tiny" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: m.fits ? "#e6edf3" : "#7d8590" }}>
                  {m.id}
                </div>
                <div className="tiny mute">
                  {m.est_gb} GB {m.tier} · {m.downloads?.toLocaleString?.() ?? 0} downloads {!m.fits && "· too large"}
                </div>
              </div>
              <Button size="sm" disabled={!m.fits || downloading === m.id} onClick={() => void downloadModel(m)}>
                {downloading === m.id ? <Loader2 size={12} className="animate-spin" /> : <Cpu size={12} />} Download
              </Button>
            </div>
          ))}
          {!models.data && <span className="tiny mute">loading recommendations…</span>}
        </div>
      </Panel>

      <Panel title="Support tools" actions={<Badge tone={toolResults ? "ok" : "dim"}>{toolResults ? "checked" : "not run"}</Badge>}>
        <p className="tiny mute" style={{ margin: "0 0 10px" }}>
          Installs missing dependencies (Frida, apktool, jadx, Wireshark/tshark, ngrok) into ~/.pegasus/tools and adds them to PATH.
          Tools already installed are skipped.
        </p>
        <Button size="sm" onClick={() => void installTools()} disabled={installing}>
          {installing ? "Installing…" : "Install missing tools"}
        </Button>
        {toolResults && (
          <div style={{ display: "grid", gap: 4, marginTop: 10 }}>
            {toolResults.map((t) => (
              <div key={t.key} className="row" style={{ gap: 8 }}>
                <span className="mono tiny" style={{ width: 90 }}>{t.key}</span>
                <span className={`mono tiny ${t.status === "error" ? "text-red-400" : t.status === "present" ? "text-slate-500" : "text-green-400"}`}>
                  {t.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {err && <div className="mono tiny" style={{ color: "#f85149", marginTop: 10 }}>⚠ {err}</div>}

      <div className="row" style={{ gap: 10, marginTop: 22 }}>
        <Button onClick={() => void submit()} disabled={busy}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <KeyRound size={13} />} Save & continue
        </Button>
        <Button variant="ghost" onClick={() => void skip()} disabled={busy}>
          Skip — local only <ArrowRight size={12} />
        </Button>
      </div>
    </div>
  );
}
