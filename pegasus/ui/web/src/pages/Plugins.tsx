import { useState } from "react";
import { Boxes, ChevronRight, Cpu, Puzzle, RefreshCw, Shield, Terminal } from "lucide-react";
import { useApi } from "@/lib/api";
import type { PluginInfo } from "@/lib/types";
import { Badge, Button, Empty, PageHeader, Panel, Stat } from "@/components/ui";
import { titleCase } from "@/lib/format";

export default function Plugins() {
  const { data, loading, refresh } = useApi<{ plugins: PluginInfo[]; count: number; error?: string }>(
    "/plugins",
    { interval: 30000 },
  );
  const [selected, setSelected] = useState<string | null>(null);
  const plugins = data?.plugins ?? [];
  const active = plugins.find((plugin) => plugin.name === selected) ?? plugins[0];

  const categories = new Set(plugins.map((plugin) => plugin.category));

  return (
    <div className="page">
      <PageHeader
        title="Plugins"
        subtitle="Loaded modules, their commands and UI contributions"
        actions={<Button size="sm" onClick={refresh}><RefreshCw size={12} /> Reload registry</Button>}
      />

      <div className="stat-grid">
        <Stat value={plugins.length} label="Plugins loaded" tone="info" />
        <Stat value={plugins.reduce((acc, plugin) => acc + plugin.commands.length, 0)} label="Commands exposed" />
        <Stat value={categories.size} label="Categories" />
        <Stat value={plugins.filter((plugin) => plugin.initialized).length} label="Initialized" tone="ok" />
      </div>

      {loading && !data ? (
        <Panel title="Plugin registry"><div className="tiny mute">Loading…</div></Panel>
      ) : plugins.length === 0 ? (
        <Panel title="Plugin registry">
          <Empty icon={<Puzzle size={16} />} title="No plugins loaded" detail={data?.error ?? "Check the plugin discovery paths."} />
        </Panel>
      ) : (
        <div className="split">
          <Panel title="Registry" tight>
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Plugin</th><th>Version</th><th>Category</th><th>Commands</th><th /></tr></thead>
                <tbody>
                  {plugins.map((plugin) => (
                    <tr
                      key={plugin.name}
                      onClick={() => setSelected(plugin.name)}
                      style={{ cursor: "pointer", background: active?.name === plugin.name ? "rgba(255,61,0,.05)" : undefined }}
                    >
                      <td>
                        <div className="td-strong">{plugin.name}</div>
                        <div className="tiny mute td-truncate" style={{ maxWidth: 280 }}>{plugin.description}</div>
                      </td>
                      <td className="mono tiny">{plugin.version}</td>
                      <td><Badge tone="dim">{plugin.category}</Badge></td>
                      <td className="mono tiny">{plugin.commands.length}</td>
                      <td><ChevronRight size={13} className="mute" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {active && (
            <div className="col">
              <Panel title={`${active.name} v${active.version}`} actions={<Badge tone={active.initialized ? "ok" : "warn"}>{active.initialized ? "initialized" : "pending"}</Badge>}>
                <div className="small" style={{ lineHeight: 1.7 }}>{active.description}</div>
                <div className="tag-row" style={{ marginTop: 10 }}>
                  {active.tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
                </div>
                <div className="kv" style={{ marginTop: 12 }}><span className="kv-k">Author</span><span className="kv-v">{active.author || "—"}</span></div>
                <div className="kv"><span className="kv-k">Category</span><span className="kv-v">{titleCase(active.category)}</span></div>
                <div className="kv"><span className="kv-k">UI modules</span><span className="kv-v mono tiny">{active.components.length}</span></div>
              </Panel>

              <Panel title="Commands" tight>
                {active.commands.length === 0 ? (
                  <Empty icon={<Terminal size={14} />} title="No commands" detail="This plugin contributes hooks only." />
                ) : (
                  <div style={{ maxHeight: 280, overflowY: "auto" }}>
                    {active.commands.map((cmd) => (
                      <div className="row" key={cmd.name} style={{ padding: "8px 14px", borderBottom: "1px solid var(--line-soft)", gap: 10 }}>
                        <Shield size={11} className="orange" />
                        <div style={{ flex: 1 }}>
                          <div className="mono tiny strong">{cmd.name}</div>
                          <div className="tiny mute td-truncate" style={{ maxWidth: 280 }}>{cmd.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>

              {active.components.length > 0 && (
                <Panel title="UI contributions">
                  <div className="col" style={{ gap: 0 }}>
                    {active.components.map((component) => (
                      <div className="kv" key={component.name}>
                        <span className="kv-k">{component.title}</span>
                        <span className="kv-v mono tiny">{component.path}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
