import { useState } from "react";
import { Copy, Cpu, FolderTree, KeyRound, RefreshCw, Server, Settings as SettingsIcon } from "lucide-react";
import { useApp } from "@/state/AppContext";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, PageHeader, Panel, Stat, Terminal } from "@/components/ui";
import type { HealthInfo, ToolStatus } from "@/lib/types";
import { formatDateTime } from "@/lib/format";

const ENV_KEYS = [
  "PEGASUS__AI__API_KEY",
  "PEGASUS__AI__MODEL",
  "PEGASUS__METASPLOIT__RPC_HOST",
  "PEGASUS__METASPLOIT__RPC_PORT",
  "PEGASUS__METASPLOIT__RPC_PASSWORD",
  "PEGASUS__DATABASE__TYPE",
  "PEGASUS__DATABASE__PATH",
  "PEGASUS__SECURITY__JWT_SECRET",
];

export default function Settings() {
  const { system, refreshSystem, activeSerial } = useApp();
  const [copied, setCopied] = useState<string | null>(null);
  const health = useApi<HealthInfo>("/health", { interval: 15000 });
  const tools = useApi<{ tools: ToolStatus[] }>("/system/tools", { interval: 45000 });

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      window.setTimeout(() => setCopied(null), 1400);
    } catch {
      /* clipboard blocked */
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Settings"
        subtitle="Environment, workspace paths and platform configuration"
        actions={<Button size="sm" onClick={() => void refreshSystem()}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={health.data?.status ?? "—"} label="API health" tone={health.data?.status === "online" ? "ok" : "warn"} />
        <Stat value={health.data ? `${Math.floor(health.data.uptimeSeconds / 60)}m` : "—"} label="Uptime" />
        <Stat value={system?.workspace.aiConfigured ? "SET" : "UNSET"} label="AI key" tone={system?.workspace.aiConfigured ? "ok" : "warn"} />
        <Stat value={activeSerial ? "BOUND" : "IDLE"} label="Active device" hint={activeSerial ?? "none"} />
      </div>

      <div className="grid-2">
        <Panel title="Workspace paths">
          <div className="col" style={{ gap: 0 }}>
            {[
              { icon: <FolderTree size={12} />, label: "Workspace", value: system?.workspace.workspace },
              { icon: <Server size={12} />, label: "Database", value: system?.workspace.databasePath },
              { icon: <FolderTree size={12} />, label: "Reports", value: system?.workspace.reportsDir },
              { icon: <FolderTree size={12} />, label: "Payloads", value: system?.workspace.payloadsDir },
              { icon: <FolderTree size={12} />, label: "Logs", value: system?.workspace.logsDir },
            ].map((row) => (
              <div className="kv" key={row.label}>
                <span className="kv-k row" style={{ gap: 6 }}>{row.icon}{row.label}</span>
                <span className="kv-v mono tiny td-truncate" style={{ maxWidth: 330 }}>{row.value ?? "—"}</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Environment">
          <div className="col" style={{ gap: 0 }}>
            <div className="kv"><span className="kv-k">Hostname</span><span className="kv-v mono tiny">{system?.environment.hostname ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Local IP</span><span className="kv-v mono tiny">{system?.environment.localIp ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Python</span><span className="kv-v mono tiny">{system?.environment.python ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Platform</span><span className="kv-v mono tiny td-truncate" style={{ maxWidth: 300 }}>{system?.environment.platform ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Process</span><span className="kv-v mono tiny">pid {system?.environment.pid ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">CWD</span><span className="kv-v mono tiny td-truncate" style={{ maxWidth: 300 }}>{system?.environment.cwd ?? "—"}</span></div>
            <div className="kv"><span className="kv-k">Version</span><span className="kv-v mono tiny">v{system?.workspace.version ?? "—"}</span></div>
          </div>
        </Panel>
      </div>

      <Panel title="Services">
        <div className="grid-2">
          {(system?.components ?? []).map((component) => (
            <div className="cmd-card" key={component.name} style={{ cursor: "default" }}>
              <div className="cmd-name">
                <span className="row" style={{ gap: 7 }}><Cpu size={12} />{component.name}</span>
                <Badge tone={component.status === "online" ? "ok" : component.status === "degraded" ? "warn" : "dim"}>
                  {component.status}
                </Badge>
              </div>
              <div className="cmd-desc mono tiny td-truncate">{component.detail}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Configuration variables" actions={<Badge tone="dim">.env</Badge>}>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>Variable</th><th>Purpose</th><th /></tr></thead>
            <tbody>
              {ENV_KEYS.map((key) => (
                <tr key={key}>
                  <td className="mono tiny td-strong">{key}</td>
                  <td className="tiny mute">{purpose(key)}</td>
                  <td>
                    <Button size="xs" variant="ghost" onClick={() => void copy(key)}>
                      <Copy size={11} /> {copied === key ? "copied" : "copy"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Toolchain readiness" muted>
        <div className="grid-4">
          {(tools.data?.tools ?? []).map((tool) => (
            <div className="cmd-card" key={tool.key} style={{ cursor: "default", gap: 5 }}>
              <div className="cmd-name">
                <span className="small">{tool.label}</span>
                <Badge tone={tool.available ? "ok" : tool.required === "yes" ? "err" : "dim"}>{tool.available ? "ok" : "missing"}</Badge>
              </div>
              <div className="tiny mono mute td-truncate">{tool.version ?? "—"}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Operations console" muted>
        <Terminal
          lines={[
            { text: "pegasus serve            # web GUI (this server)", tone: "cmd" },
            { text: "pegasus menu             # interactive TUI", tone: "cmd" },
            { text: "pegasus plugins          # list plugins", tone: "cmd" },
            { text: "pegasus run cve-scan     # execute a command", tone: "cmd" },
            { text: "pegasus slash adb-devices # slash command bridge", tone: "cmd" },
            { text: "", tone: "dim" },
            { text: `web bundle: cd pegasus/ui/web && npm install && npm run build`, tone: "dim" },
            { text: `last health check: ${formatDateTime(Date.now())}`, tone: "dim" },
          ]}
          title="cli reference"
          maxHeight={200}
        />
      </Panel>
    </div>
  );
}

function purpose(key: string): string {
  if (key.includes("AI__API_KEY")) return "Anthropic API key for the AI assistant";
  if (key.includes("AI__MODEL")) return "Model id used by AI features";
  if (key.includes("RPC_HOST")) return "Metasploit RPC host";
  if (key.includes("RPC_PORT")) return "Metasploit RPC port (default 55553)";
  if (key.includes("RPC_PASSWORD")) return "Metasploit RPC password";
  if (key.includes("DATABASE__TYPE")) return "sqlite or postgresql";
  if (key.includes("DATABASE__PATH")) return "SQLite database file path";
  if (key.includes("JWT_SECRET")) return "JWT signing secret for the API";
  return "—";
}
