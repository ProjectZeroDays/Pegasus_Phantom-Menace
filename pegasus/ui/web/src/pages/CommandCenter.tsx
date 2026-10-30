import { useMemo, useState } from "react";
import { Command, Play, Search, Terminal } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { CommandInfo, Job } from "@/lib/types";
import { Badge, Button, Empty, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { JobOutput } from "@/components/JobDrawer";

export default function CommandCenter() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | string>("all");
  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const { data, loading } = useApi<{ commands: CommandInfo[]; count: number }>("/commands", { interval: 30000 });

  const plugins = useMemo(() => {
    const set = new Set((data?.commands ?? []).map((cmd) => cmd.plugin));
    return ["all", ...[...set].sort()];
  }, [data]);

  const rows = useMemo(() => {
    let list = data?.commands ?? [];
    if (filter !== "all") list = list.filter((cmd) => cmd.plugin === filter);
    if (query.trim()) {
      const needle = query.toLowerCase();
      list = list.filter(
        (cmd) =>
          cmd.name.toLowerCase().includes(needle) ||
          cmd.description.toLowerCase().includes(needle),
      );
    }
    return list;
  }, [data, filter, query]);

  const run = async (name: string) => {
    setRunning(name);
    try {
      const result = await api.post<{ job: Job }>(`/commands/${name}/run`, { args: [] });
      setJobId(result.job.id);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Command Center"
        subtitle="Every registered plugin command with live dispatch"
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 240 }} placeholder="search command or description" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.commands.length ?? "—"} label="Registered commands" tone="info" />
        <Stat value={plugins.length - 1} label="Owning plugins" />
        <Stat value={rows.length} label="Visible after filter" />
        <Stat value="isolated" label="Execution model" hint="thread per job" />
      </div>

      <Panel
        title="Command registry"
        actions={
          <Segmented
            value={filter}
            onChange={setFilter}
            options={plugins.map((plugin) => ({ value: plugin, label: plugin === "all" ? "All" : plugin }))}
          />
        }
      >
        {loading && !data ? (
          <div className="tiny mute">Loading registry…</div>
        ) : rows.length === 0 ? (
          <Empty icon={<Command size={16} />} title="No commands match" detail="Adjust the filter or search term." />
        ) : (
          <div className="grid-3">
            {rows.map((cmd) => (
              <div className="cmd-card" key={cmd.name} style={{ cursor: "default" }}>
                <div className="cmd-name">
                  <span className="mono">{cmd.name}</span>
                  <Badge tone="primary">{cmd.plugin}</Badge>
                </div>
                <div className="cmd-desc">{cmd.description}</div>
                {cmd.aliases.length > 0 && (
                  <div className="tag-row">
                    {cmd.aliases.map((alias) => <span className="tag" key={alias}>{alias}</span>)}
                  </div>
                )}
                <div className="row">
                  <Button size="xs" variant="primary" disabled={running === cmd.name} onClick={() => void run(cmd.name)}>
                    <Play size={10} /> {running === cmd.name ? "dispatching" : "run"}
                  </Button>
                  <span className="tiny mute mono">pegasus {cmd.name}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {jobId && (
        <Panel title="Execution output">
          <JobOutput jobId={jobId} title="command" height={340} />
        </Panel>
      )}
    </div>
  );
}
