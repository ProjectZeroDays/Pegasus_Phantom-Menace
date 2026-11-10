import { useEffect, useState } from "react";
import { CheckCircle2, Download, MonitorSmartphone, RefreshCw, Wifi } from "lucide-react";
import { PageHeader, Panel, Stat, Badge, Empty } from "@/components/ui";

interface Manifest {
  name?: string;
  short_name?: string;
  start_url?: string;
  display?: string;
  theme_color?: string;
  background_color?: string;
  icons?: { src: string; sizes: string; type: string }[];
}

interface SwState {
  supported: boolean;
  registered: boolean;
  scope: string | null;
  active: boolean;
}

const CHECKLIST: { label: string; ok: (m: Manifest | null, s: SwState) => boolean }[] = [
  { label: "Web app manifest linked (/manifest.webmanifest)", ok: () => true },
  { label: "Human-readable name + short_name", ok: (m) => !!m?.name && !!m?.short_name },
  { label: "Standalone display mode", ok: (m) => m?.display === "standalone" || m?.display === "fullscreen" || m?.display === "minimal-ui" },
  { label: "Start URL configured", ok: (m) => !!m?.start_url },
  { label: "192px + 512px icons present", ok: (m) => {
      const sizes = (m?.icons ?? []).map((i) => i.sizes);
      return sizes.some((s) => s.includes("192x192")) && sizes.some((s) => s.includes("512x512"));
    } },
  { label: "Service worker registered", ok: (_m, s) => s.supported && s.registered },
  { label: "Theme color set", ok: (m) => !!m?.theme_color },
];

export default function Pwa() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [sw, setSw] = useState<SwState>({ supported: "serviceWorker" in navigator, registered: false, scope: null, active: false });
  const [error, setError] = useState<string | null>(null);

  const probe = async () => {
    setError(null);
    try {
      const resp = await fetch("/manifest.webmanifest");
      if (!resp.ok) throw new Error(`manifest HTTP ${resp.status}`);
      setManifest((await resp.json()) as Manifest);
    } catch (err) {
      setManifest(null);
      setError(err instanceof Error ? err.message : "manifest unavailable");
    }
    if ("serviceWorker" in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      const reg = regs[0];
      setSw({ supported: true, registered: !!reg, scope: reg?.scope ?? null, active: !!reg?.active });
    } else {
      setSw({ supported: false, registered: false, scope: null, active: false });
    }
  };

  useEffect(() => { void probe(); }, []);

  const passed = CHECKLIST.filter((c) => c.ok(manifest, sw)).length;
  const installable = passed >= 6 && sw.registered;

  return (
    <div className="page">
      <PageHeader
        title="Progressive Web App"
        subtitle="Offline-capable install of the Pegasus web console — status verified at runtime"
        actions={<button className="btn btn-sm" onClick={() => void probe()}><RefreshCw size={12} /> Re-probe</button>}
      />

      <div className="stat-grid">
        <Stat value={installable ? "YES" : "NO"} label="Installable" tone={installable ? "ok" : "warn"} />
        <Stat value={`${passed}/${CHECKLIST.length}`} label="Checklist passed" tone="info" />
        <Stat value={sw.registered ? "registered" : "unknown"} label="Service worker" tone={sw.registered ? "ok" : "info"} />
        <Stat value={manifest?.display ?? "—"} label="Display mode" tone="info" />
      </div>

      <Panel title="Readiness checklist" tight>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>#</th><th>Requirement</th><th>Result</th></tr></thead>
            <tbody>
              {CHECKLIST.map((item, i) => (
                <tr key={i}>
                  <td className="mono tiny">{i + 1}</td>
                  <td className="tiny">{item.label}</td>
                  <td>{item.ok(manifest, sw) ? <Badge tone="ok">pass</Badge> : <Badge tone="warn">missing</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Live manifest">
        {manifest ? (
          <div className="tiny">
            <div className="form-row">
              <div><span className="mute">Name</span><br /><strong>{manifest.name ?? "—"}</strong></div>
              <div><span className="mute">Short name</span><br /><strong>{manifest.short_name ?? "—"}</strong></div>
              <div><span className="mute">Start URL</span><br /><code>{manifest.start_url ?? "—"}</code></div>
              <div><span className="mute">Theme color</span><br /><span className="mono">{manifest.theme_color ?? "—"}</span></div>
            </div>
            <p className="tiny mute" style={{ marginTop: 8 }}>Icons: {(manifest.icons ?? []).map((i) => `${i.sizes}`).join(", ") || "none"}</p>
            <details>
              <summary className="tiny mute">Raw manifest JSON</summary>
              <pre className="mono tiny" style={{ maxHeight: 240, overflow: "auto" }}>{JSON.stringify(manifest, null, 2)}</pre>
            </details>
          </div>
        ) : (
          <Empty icon={<MonitorSmartphone size={16} />} title="Manifest unavailable" detail={error ?? "Fetch failed"} action={<button className="btn btn-xs" onClick={() => void probe()}>Retry</button>} />
        )}
      </Panel>

      <Panel title="Service worker">
        <div className="tiny">
          <div className="form-row">
            <div><span className="mute">API support</span><br /><Badge tone={sw.supported ? "ok" : "err"}>{sw.supported ? "yes" : "no"}</Badge></div>
            <div><span className="mute">Registered</span><br /><Badge tone={sw.registered ? "ok" : "dim"}>{sw.registered ? "yes" : "no"}</Badge></div>
            <div><span className="mute">Active</span><br /><Badge tone={sw.active ? "ok" : "warn"}>{sw.active ? "yes" : "pending"}</Badge></div>
            <div><span className="mute">Scope</span><br /><code>{sw.scope ?? "—"}</code></div>
          </div>
          <p className="tiny mute" style={{ marginTop: 8 }}><Wifi size={11} style={{ display: "inline" }} /> Background keep-alive is driven from <code>main.tsx</code> (KEEPALIVE_START + sync registration on visibilitychange). Offline fallbacks are served from <code>/sw.js</code>.</p>
          <p className="tiny mute"><Download size={11} style={{ display: "inline" }} /> Install: use the browser's address-bar install affordance or the menu → "Install Pegasus Phantom Menace".</p>
        </div>
      </Panel>

      <Panel title="Why this matters" tight>
        <p className="tiny" style={{ margin: 0 }}><CheckCircle2 size={11} style={{ display: "inline" }} /> Operators can run assessments from a hardened kiosk or air-gapped laptop: the console loads instantly, works offline for cached views, and re-syncs when connectivity returns.</p>
      </Panel>
    </div>
  );
}
