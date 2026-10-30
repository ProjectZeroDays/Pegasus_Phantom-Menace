import { useMemo, useState } from "react";
import {
  Bluetooth, Cable, Crosshair, Fingerprint, Grid3x3, QrCode, Radio, Rocket,
  ShieldCheck, Smartphone, Trophy, Usb, Wifi, Zap,
} from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Panel, PageHeader, Progress, Segmented, Terminal } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { titleCase } from "@/lib/format";

interface VectorCard {
  id: string;
  label: string;
  detail: string;
  icon: React.ReactNode;
  command: string;
  tone: "ok" | "warn" | "dim";
}

const VECTORS: VectorCard[] = [
  { id: "adb", label: "ADB", detail: "Debug bridge over TCP 5555 or USB", icon: <Cable size={14} />, command: "adb-devices", tone: "ok" },
  { id: "fastboot", label: "Fastboot", detail: "Bootloader mode, OEM unlock", icon: <Usb size={14} />, command: "fastboot-devices", tone: "dim" },
  { id: "qr_pairing", label: "QR pairing", detail: "Android 11+ wireless debugging", icon: <QrCode size={14} />, command: "wireless-adb", tone: "ok" },
  { id: "usb", label: "USB", detail: "MTP + ADB debugging session", icon: <Usb size={14} />, command: "adb-devices", tone: "ok" },
  { id: "zero_click", label: "Zero-click", detail: "Pixel 8 / S24 / Xiaomi chains", icon: <Zap size={14} />, command: "access-zero-click", tone: "ok" },
  { id: "bluetooth", label: "Bluetooth", detail: "Proximity discovery and pairing", icon: <Bluetooth size={14} />, command: "btscan", tone: "warn" },
  { id: "wifi", label: "Wi-Fi", detail: "Beacon scan and evil-twin hooks", icon: <Wifi size={14} />, command: "wifiscan", tone: "ok" },
  { id: "nfc", label: "NFC", detail: "Tag emulation and relay", icon: <Radio size={14} />, command: "netscan", tone: "dim" },
];

const STEPS = [
  "Discover vectors",
  "Fingerprint target",
  "Select exploit",
  "Execute chain",
  "Establish access",
  "Hand off to post-exploitation",
];

export default function AccessWorkflow() {
  const { activeSerial, devices } = useApp();
  const [mode, setMode] = useState<"manual" | "autonomous">("autonomous");
  const [jobId, setJobId] = useState<string | null>(null);
  const [target, setTarget] = useState("");
  const [vectorFilter, setVectorFilter] = useState<string>("all");

  const commands = useApi<{ commands: { name: string; description: string; plugin: string }[] }>("/commands");

  const status = useApi<{ devices: { serial: string; state: string }[] }>("/devices", { interval: 25000 });
  const online = useMemo(
    () => new Set((status.data?.devices ?? []).map((d) => d.serial)),
    [status.data],
  );

  const run = async (name: string, args: string[] = []) => {
    const data = await api.post<{ job: Job }>(`/commands/${name}/run`, { args });
    setJobId(data.job.id);
  };

  const launchAutonomous = async () => {
    const data = await api.post<{ job: Job }>("/workflows/run", {
      target: target || activeSerial || "127.0.0.1",
      category: "full_lifecycle",
    });
    setJobId(data.job.id);
  };

  const filtered = vectorFilter === "all" ? VECTORS : VECTORS.filter((v) => v.id === vectorFilter);

  return (
    <div className="page">
      <PageHeader
        title="Access Workflow"
        subtitle="Manual vector control and autonomous lifecycle orchestration"
        actions={
          <Segmented
            value={mode}
            onChange={setMode}
            options={[
              { value: "manual", label: "Manual", icon: <Grid3x3 size={12} /> },
              { value: "autonomous", label: "Autonomous", icon: <Rocket size={12} /> },
            ]}
          />
        }
      />

      <div className="stat-grid">
        <div className="stat info">
          <div className="stat-value" style={{ fontSize: 18 }}>{devices.length}</div>
          <div className="stat-label">Reachable endpoints</div>
          <div className="stat-hint">{online.size} reporting as device</div>
        </div>
        <div className="stat ok">
          <div className="stat-value" style={{ fontSize: 18 }}>{VECTORS.length}</div>
          <div className="stat-label">Access vectors</div>
          <div className="stat-hint">ADB · Fastboot · QR · USB · Zero-click</div>
        </div>
        <div className="stat warn">
          <div className="stat-value" style={{ fontSize: 18 }}>12</div>
          <div className="stat-label">Lifecycle stages</div>
          <div className="stat-hint">Recon → cleanup</div>
        </div>
        <div className="stat">
          <div className="stat-value" style={{ fontSize: 18 }}>{activeSerial ? "BOUND" : "IDLE"}</div>
          <div className="stat-label">Target binding</div>
          <div className="stat-hint td-truncate">{activeSerial ?? "select a device"}</div>
        </div>
      </div>

      {mode === "manual" ? (
        <Panel
          title="Manual vector controls"
          actions={
            <select className="select" style={{ width: 190 }} value={vectorFilter} onChange={(e) => setVectorFilter(e.target.value)}>
              <option value="all">All vectors</option>
              {VECTORS.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
            </select>
          }
        >
          <div className="grid-3">
            {filtered.map((vector) => (
              <div className="cmd-card" key={vector.id} style={{ cursor: "default" }}>
                <div className="cmd-name">
                  <span className="row" style={{ gap: 7 }}>{vector.icon}{vector.label}</span>
                  <Badge tone={vector.tone}>{vector.tone === "ok" ? "available" : vector.tone === "warn" ? "conditional" : "unavailable"}</Badge>
                </div>
                <div className="cmd-desc">{vector.detail}</div>
                <div className="row" style={{ gap: 6 }}>
                  <Button size="xs" variant="primary" onClick={() => void run(vector.command)}>
                    <Crosshair size={11} /> Probe
                  </Button>
                  <Button size="xs" onClick={() => void run("access-vectors")}>Enumerate</Button>
                </div>
              </div>
            ))}
          </div>

          <div className="grid-3" style={{ marginTop: 14 }}>
            <Button size="sm" onClick={() => void run("access-manual")}>Interactive manual menu</Button>
            <Button size="sm" onClick={() => void run("access-menu")}>Access workflow menu</Button>
            <Button size="sm" onClick={() => void run("fingerprint", activeSerial ? [activeSerial] : [])}>Fingerprint device</Button>
          </div>
        </Panel>
      ) : (
        <Panel title="Autonomous lifecycle">
          <div className="form-row">
            <label className="field">
              <span className="field-label">Target</span>
              <input
                className="input"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder={activeSerial ?? "192.168.1.105"}
              />
            </label>
            <label className="field">
              <span className="field-label">Bind to active device</span>
              <button
                className="btn"
                onClick={() => setTarget(activeSerial ?? "")}
                disabled={!activeSerial}
              >
                <Smartphone size={12} /> {activeSerial ?? "no device"}
              </button>
            </label>
            <label className="field">
              <span className="field-label">Launch</span>
              <button className="btn btn-primary" onClick={() => void launchAutonomous()}>
                <Rocket size={13} /> Run full lifecycle
              </button>
            </label>
          </div>

          <div className="col" style={{ gap: 8, marginTop: 16 }}>
            {STEPS.map((step, index) => (
              <div className="row" key={step} style={{ gap: 10 }}>
                <span
                  className="mono tiny"
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 6,
                    border: "1px solid var(--line)",
                    display: "grid",
                    placeItems: "center",
                    color: "var(--ink-dim)",
                  }}
                >
                  {index + 1}
                </span>
                <span className="small">{step}</span>
                <span className="spacer" />
                <span className="tiny mute">stage {index + 1}/6</span>
              </div>
            ))}
          </div>

          <div className="tiny mute" style={{ marginTop: 12 }}>
            The engine self-heals: failed vectors are retried with an alternate chain, and each stage
            records an adaptive decision to the workflow log.
          </div>
        </Panel>
      )}

      <Panel
        title="Vector telemetry"
        actions={<Badge tone="dim">workflow engine</Badge>}
      >
        <div className="grid-4">
          {[
            { icon: <Fingerprint size={13} />, label: "Recon", detail: "mDNS, TCP 5555, BT/LE" },
            { icon: <Trophy size={13} />, label: "Exploit select", detail: "CVE + AV ranking" },
            { icon: <ShieldCheck size={13} />, label: "Access", detail: "persistence checks" },
            { icon: <Zap size={13} />, label: "Post", detail: "credential + exfil" },
          ].map((item) => (
            <div className="cmd-card" key={item.label} style={{ cursor: "default" }}>
              <div className="cmd-name">{item.icon}{item.label}</div>
              <div className="cmd-desc">{item.detail}</div>
            </div>
          ))}
        </div>
      </Panel>

      {jobId && (
        <Panel title="Execution output">
          <JobOutput jobId={jobId} title="access workflow" height={340} />
        </Panel>
      )}

      {!jobId && (
        <Panel title="Registered access commands" muted>
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>Command</th><th>Description</th><th>Plugin</th><th /></tr>
              </thead>
              <tbody>
                {(commands.data?.commands ?? [])
                  .filter((cmd) => cmd.plugin === "access_workflow" || cmd.plugin === "post_exploitation")
                  .map((cmd) => (
                    <tr key={cmd.name}>
                      <td className="mono td-strong">{cmd.name}</td>
                      <td className="tiny dim td-truncate">{cmd.description}</td>
                      <td><Badge tone="dim">{cmd.plugin}</Badge></td>
                      <td>
                        <Button size="xs" onClick={() => void run(cmd.name)}>run</Button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
