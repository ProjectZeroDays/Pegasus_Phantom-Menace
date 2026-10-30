import { useState } from "react";
import { Flame, Radar, ShieldAlert, Target, Zap } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { CveEntry, Job } from "@/lib/types";
import { Badge, Button, Empty, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { severityClass } from "@/lib/format";
import { useApp } from "@/state/AppContext";

const ZERO_CLICK_MODULES = [
  { id: "pixel8", label: "Pixel 8", detail: "Modem, Wi-Fi, Titan M2, NFC chains", command: "access-zero-click" },
  { id: "samsung", label: "Samsung S24", detail: "Exynos baseband + Knox surface", command: "access-zero-click" },
  { id: "xiaomi", label: "Xiaomi 13T", detail: "MIUI / HyperOS messenger vector", command: "access-zero-click" },
  { id: "oneplus", label: "OnePlus", detail: "OxygenOS deep-link chains", command: "access-zero-click" },
  { id: "android", label: "AOSP general", detail: "Stagefright-class media parsers", command: "access-zero-click" },
  { id: "tv", label: "Android TV", detail: "TV input framework exploitation", command: "exploit" },
];

export default function ZeroClick() {
  const { activeSerial } = useApp();
  const [tab, setTab] = useState<"vectors" | "cve">("vectors");
  const [jobId, setJobId] = useState<string | null>(null);

  const cves = useApi<{ cves: CveEntry[]; count: number }>("/cve");
  const rank = (severity: string) =>
    ({ Critical: 4, High: 3, Medium: 2, Low: 1 } as Record<string, number>)[severity] ?? 0;
  const sorted = [...(cves.data?.cves ?? [])].sort((a, b) => b.cvss - a.cvss);

  const run = async (command: string) => {
    const data = await api.post<{ job: Job }>(`/commands/${command}/run`, { args: [] });
    setJobId(data.job.id);
  };

  const scan = async () => {
    const data = await api.post<{ job: Job }>("/cve/scan", { serial: activeSerial });
    setJobId(data.job.id);
  };

  const critical = sorted.filter((cve) => cve.severity === "Critical").length;

  return (
    <div className="page">
      <PageHeader
        title="Zero-Click & CVE"
        subtitle="Remote chains without user interaction, correlated with the CVE database"
        actions={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "vectors", label: "Zero-click", icon: <Zap size={12} /> },
              { value: "cve", label: "CVE database", icon: <ShieldAlert size={12} /> },
            ]}
          />
        }
      />

      <div className="stat-grid">
        <Stat value={sorted.length} label="CVEs in database" hint={`${critical} critical severity`} tone="warn" />
        <Stat value={ZERO_CLICK_MODULES.length} label="Zero-click families" hint="Pixel · Samsung · Xiaomi · TV" tone="info" />
        <Stat value={activeSerial ? "READY" : "NO DEVICE"} label="Scan target" hint={activeSerial ?? "select a device"} />
        <Stat value="0-CLICK" label="User interaction" hint="messenger / modem / NFC delivery" tone="ok" />
      </div>

      {tab === "vectors" ? (
        <>
          <Panel
            title="Zero-click exploit menu"
            actions={
              <>
                <Button size="sm" onClick={() => void run("access-zero-click")}>
                  <Flame size={12} /> Open exploit menu
                </Button>
                <Button size="sm" variant="primary" onClick={() => void run("access-autonomous")}>
                  <Radar size={12} /> Auto-select
                </Button>
              </>
            }
          >
            <div className="grid-3">
              {ZERO_CLICK_MODULES.map((module) => (
                <div className="cmd-card" key={module.id} style={{ cursor: "default" }}>
                  <div className="cmd-name">
                    <span className="row" style={{ gap: 7 }}><Target size={13} />{module.label}</span>
                    <Badge tone="primary">0-click</Badge>
                  </div>
                  <div className="cmd-desc">{module.detail}</div>
                  <Button size="xs" variant="primary" onClick={() => void run(module.command)}>Deploy</Button>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Related commands" muted>
            <div className="grid-4">
              {["access-zero-click", "access-autonomous", "access-vectors", "exploit", "post-exploitation", "frp-bypass"].map((name) => (
                <button key={name} className="cmd-card" onClick={() => void run(name)}>
                  <div className="cmd-name">{name}</div>
                  <div className="cmd-desc">dispatch to plugin command runtime</div>
                </button>
              ))}
            </div>
          </Panel>
        </>
      ) : (
        <Panel
          title="Android CVE database"
          tight
          actions={
            <>
              <Badge tone="dim">{sorted.length} entries</Badge>
              <Button size="sm" variant="primary" onClick={() => void scan()} disabled={!activeSerial}>
                <ShieldAlert size={12} /> Scan {activeSerial ?? "device"}
              </Button>
            </>
          }
        >
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>CVE</th><th>Severity</th><th>CVSS</th><th>Affected API</th><th>Patch</th><th>Description</th></tr>
              </thead>
              <tbody>
                {sorted.map((cve) => (
                  <tr key={cve.id}>
                    <td className="mono td-strong">{cve.id}</td>
                    <td><span className={severityClass(cve.severity)}>{cve.severity}</span></td>
                    <td className="mono">{cve.cvss.toFixed(1)}</td>
                    <td className="mono tiny">{cve.affected_api_min}–{cve.affected_api_max}</td>
                    <td className="mono tiny">{cve.patch_level}</td>
                    <td className="td-truncate tiny dim" style={{ maxWidth: 460 }}>{cve.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {jobId && (
        <Panel title="Execution output">
          <JobOutput jobId={jobId} title="zero-click / cve" height={320} />
        </Panel>
      )}
    </div>
  );
}
