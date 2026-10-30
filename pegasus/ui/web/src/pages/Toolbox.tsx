import { useMemo, useState } from "react";
import { Play, RefreshCw, Terminal, Wrench } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Job, SlashCommandInfo, ToolStatus } from "@/lib/types";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";
import { titleCase } from "@/lib/format";

export default function Toolbox() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [selection, setSelection] = useState<string>("adb");
  const [args, setArgs] = useState("devices -l");

  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools", { interval: 45000 });
  const slash = useApi<{ commands: SlashCommandInfo[] }>("/slash-commands", { interval: 30000 });

  const list = tools.data?.tools ?? [];
  const available = list.filter((tool) => tool.available).length;
  const current = list.find((tool) => tool.key === selection);

  const run = async () => {
    const payloadArgs = args.trim() ? args.trim().split(/\s+/) : [];
    const data = await api.post<{ job: Job }>(`/tools/${selection}/run`, { args: payloadArgs });
    setJobId(data.job.id);
  };

  const runSlash = async (name: string) => {
    const data = await api.post<{ job: Job }>(`/slash-commands/${encodeURIComponent(name)}/run`, { args: [] });
    setJobId(data.job.id);
  };

  const grouped = useMemo(() => {
    const map = new Map<string, SlashCommandInfo[]>();
    for (const cmd of slash.data?.commands ?? []) {
      map.set(cmd.category, [...(map.get(cmd.category) ?? []), cmd]);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [slash.data]);

  return (
    <div className="page">
      <PageHeader
        title="Toolbox"
        subtitle="Direct access to every binary and slash command in the platform"
        actions={<Button size="sm" onClick={() => { tools.refresh(); slash.refresh(); }}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={`${available}/${list.length}`} label="Tools available" tone={available ? "ok" : "warn"} />
        <Stat value={slash.data?.commands.length ?? "—"} label="Slash commands" tone="info" />
        <Stat value={grouped.length} label="Command categories" />
        <Stat value="sandboxed" label="Execution mode" hint="captured stdout/stderr" />
      </div>

      <div className="split">
        <Panel title="Binary console">
          <div className="form-row">
            <Field label="Binary">
              <select className="select" value={selection} onChange={(e) => setSelection(e.target.value)}>
                {list.map((tool) => (
                  <option key={tool.key} value={tool.key} disabled={!tool.available}>
                    {tool.label} {tool.available ? "" : "(missing)"}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Arguments">
              <input
                className="input"
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void run()}
                placeholder="devices -l"
              />
            </Field>
            <Field label="Execute">
              <button className="btn btn-primary" onClick={() => void run()} disabled={!current?.available}>
                <Play size={12} /> Run
              </button>
            </Field>
          </div>

          {current && (
            <div className="col" style={{ gap: 0, marginTop: 10 }}>
              <div className="kv"><span className="kv-k">Path</span><span className="kv-v mono tiny td-truncate">{current.path ?? "—"}</span></div>
              <div className="kv"><span className="kv-k">Version</span><span className="kv-v mono tiny td-truncate">{current.version ?? "—"}</span></div>
              <div className="kv"><span className="kv-k">Purpose</span><span className="kv-v tiny">{current.purpose}</span></div>
              <div className="kv"><span className="kv-k">Requirement</span><span className="kv-v"><Badge tone={current.required === "yes" ? "primary" : "dim"}>{current.required}</Badge></span></div>
            </div>
          )}

          {jobId && (
            <div style={{ marginTop: 12 }}>
              <JobOutput jobId={jobId} title={selection} height={280} />
            </div>
          )}
        </Panel>

        <Panel title="Tool inventory" tight>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Tool</th><th>State</th><th>Version</th></tr></thead>
              <tbody>
                {list.map((tool) => (
                  <tr
                    key={tool.key}
                    onClick={() => { setSelection(tool.key); setArgs(""); }}
                    style={{ cursor: "pointer" }}
                  >
                    <td className="td-strong">{tool.label}</td>
                    <td><Badge tone={tool.available ? "ok" : tool.required === "yes" ? "err" : "dim"}>{tool.available ? "ready" : "missing"}</Badge></td>
                    <td className="tiny mono mute td-truncate" style={{ maxWidth: 180 }}>{tool.version ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Panel title="Slash command palette" actions={<Badge tone="dim">{slash.data?.commands.length ?? 0} commands</Badge>}>
        {grouped.length === 0 ? (
          <Empty icon={<Terminal size={16} />} title="Slash commands unavailable" detail="The integrations module may not be loaded." />
        ) : (
          <div className="col" style={{ gap: 14 }}>
            {grouped.map(([category, commands]) => (
              <div key={category}>
                <div className="field-label" style={{ marginBottom: 6 }}>{titleCase(category)}</div>
                <div className="grid-3">
                  {commands.map((cmd) => (
                    <button key={cmd.name} className="cmd-card" onClick={() => void runSlash(cmd.name)}>
                      <div className="cmd-name">
                        <span className="mono">{cmd.name}</span>
                        <Badge tone={cmd.enabled ? "ok" : "dim"}>{cmd.enabled ? "on" : "off"}</Badge>
                      </div>
                      <div className="cmd-desc">{cmd.description}</div>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
