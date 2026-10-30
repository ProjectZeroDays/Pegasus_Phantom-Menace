import { useMemo, useState } from "react";
import { FileText, FolderDown, RefreshCw, Rocket, Wand2 } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job, PayloadFile, ToolStatus } from "@/lib/types";
import { Badge, Button, Empty, Field, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { formatBytes, formatDateTime } from "@/lib/format";

const FORMATS = ["apk", "raw", "elf", "macho", "dll", "exe", "war", "jar"];

export default function Payloads() {
  const [tab, setTab] = useState<"generate" | "library">("generate");
  const [jobId, setJobId] = useState<string | null>(null);
  const [form, setForm] = useState({
    lhost: "10.0.0.5",
    lport: 4444,
    format: "apk",
    encoder: "",
    iterations: 1,
    name: "pegasus_agent",
  });

  const files = useApi<{ payloads: PayloadFile[]; directory: string }>("/payloads", { interval: 20000 });
  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools");

  const msf = (tools.data?.tools ?? []).find((tool) => tool.key === "msfvenom");

  const generate = async () => {
    const data = await api.post<{ job: Job }>("/payloads/generate", form);
    setJobId(data.job.id);
    setTab("library");
  };

  const payloads = files.data?.payloads ?? [];
  const totalBytes = useMemo(() => payloads.reduce((acc, file) => acc + file.sizeBytes, 0), [payloads]);

  return (
    <div className="page">
      <PageHeader
        title="Payloads"
        subtitle="msfvenom generation, binding, DNA tracking and mutation"
        actions={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "generate", label: "Generate", icon: <Rocket size={12} /> },
              { value: "library", label: `Library (${payloads.length})`, icon: <FileText size={12} /> },
            ]}
          />
        }
      />

      <div className="stat-grid">
        <Stat value={payloads.length} label="Payload artifacts" tone="info" />
        <Stat value={formatBytes(totalBytes)} label="Total size" />
        <Stat value={msf?.available ? "READY" : "MISSING"} label="msfvenom" hint={msf?.version ?? "not on PATH"} tone={msf?.available ? "ok" : "warn"} />
        <Stat value={files.data?.directory ? "OK" : "—"} label="Output directory" hint={files.data?.directory ?? "—"} />
      </div>

      {tab === "generate" ? (
        <Panel title="Generate payload">
          <div className="form-row">
            <Field label="LHOST">
              <input className="input" value={form.lhost} onChange={(e) => setForm({ ...form, lhost: e.target.value })} />
            </Field>
            <Field label="LPORT">
              <input className="input" type="number" value={form.lport} onChange={(e) => setForm({ ...form, lport: Number(e.target.value) })} />
            </Field>
            <Field label="Format">
              <select className="select" value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })}>
                {FORMATS.map((format) => <option key={format} value={format}>{format}</option>)}
              </select>
            </Field>
            <Field label="Encoder">
              <input className="input" value={form.encoder} onChange={(e) => setForm({ ...form, encoder: e.target.value })} placeholder="x86/shikata_ga_nai" />
            </Field>
            <Field label="Iterations">
              <input className="input" type="number" value={form.iterations} onChange={(e) => setForm({ ...form, iterations: Number(e.target.value) })} />
            </Field>
            <Field label="Artifact name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Dispatch">
              <button className="btn btn-primary" onClick={() => void generate()}>
                <Rocket size={13} /> Generate
              </button>
            </Field>
          </div>
          <div className="tiny mute" style={{ marginTop: 10 }}>
            Generation shells out to msfvenom, captures full output, and writes the artifact into the
            workspace payloads directory.
          </div>
        </Panel>
      ) : (
        <Panel
          title="Payload library"
          tight
          actions={<Button size="sm" onClick={files.refresh}><RefreshCw size={12} /> Refresh</Button>}
        >
          {payloads.length === 0 ? (
            <Empty icon={<FolderDown size={16} />} title="No payload artifacts" detail="Generate one to populate the library." action={<Button size="sm" variant="primary" onClick={() => setTab("generate")}>Generate</Button>} />
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Artifact</th><th>Type</th><th>Size</th><th>Created</th><th>Path</th></tr></thead>
                <tbody>
                  {payloads.map((file) => (
                    <tr key={file.path}>
                      <td className="td-strong td-truncate">{file.name}</td>
                      <td><Badge tone="primary">{file.extension || "bin"}</Badge></td>
                      <td className="mono tiny">{formatBytes(file.sizeBytes)}</td>
                      <td className="tiny mute">{formatDateTime(file.createdAt)}</td>
                      <td className="mono tiny td-truncate" style={{ maxWidth: 360 }}>{file.path}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      <Panel title="Payload operations">
        <div className="grid-3">
          {[
            { command: "payload-mass", label: "Mass generation", detail: "Batch payloads with unique ports and DNA tags" },
            { command: "payload-dna", label: "DNA registry", detail: "Attribute payloads to campaigns and targets" },
            { command: "payload-mutate", label: "AI mutation", detail: "Evasion suggestions via the AI assistant" },
            { command: "payload-bind", label: "APK binding", detail: "Bind the agent into a legitimate APK" },
            { command: "payload-qr", label: "QR delivery", detail: "Generate a scannable delivery QR code" },
            { command: "payload-ssl", label: "SSL pinning bypass", detail: "Emit a Frida unpinning script" },
          ].map((item) => (
            <button
              key={item.command}
              className="cmd-card"
              onClick={async () => {
                const data = await api.post<{ job: Job }>(`/commands/${item.command}/run`, { args: [] });
                setJobId(data.job.id);
              }}
            >
              <div className="cmd-name"><span>{item.label}</span><Wand2 size={12} /></div>
              <div className="cmd-desc">{item.detail}</div>
              <span className="tag">{item.command}</span>
            </button>
          ))}
        </div>
      </Panel>

      {jobId && (
        <Panel title="Execution output">
          <JobOutput jobId={jobId} title="payload" height={320} />
        </Panel>
      )}
    </div>
  );
}
