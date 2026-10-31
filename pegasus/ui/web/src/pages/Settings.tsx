import { useEffect, useState } from "react";
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

  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("claude-sonnet-4-6");
  const [downloading, setDownloading] = useState(false);
  const [mimicodeEnabled, setMimicodeEnabled] = useState(false);

  const agentAvail = useApi<{ opencode: boolean; mimicode: boolean }>("/agents/available").data;
  const [agentCfg, setAgentCfg] = useState<{ agent: string | null; provider: string | null; model: string | null; skills: string }>({ agent: null, provider: null, model: null, skills: ".openfable-skills" });
  useEffect(() => {
    api.get<{ agent: string | null; provider: string | null; model: string | null; skills: string }>("/agents/config")
      .then((d) => setAgentCfg({ agent: d.agent, provider: d.provider, model: d.model, skills: d.skills ?? ".openfable-skills" }))
      .catch(() => undefined);
  }, []);
  const saveAgentCfg = () => api.post("/agents/config", agentCfg);

  // Telegram remote control
  const tg = useApi<{ configured: boolean; running: boolean; bot: string | null; chatId: string | null }>("/telegram/status", { interval: 20000 });
  const [tgToken, setTgToken] = useState("");
  const [tgChat, setTgChat] = useState("");
  const [tgBusy, setTgBusy] = useState(false);
  const [tgResult, setTgResult] = useState<string | null>(null);
  const saveTelegram = async () => {
    setTgBusy(true);
    setTgResult(null);
    try {
      const r = await api.post<{ bot: string; chat_id: string }>("/telegram/setup", { token: tgToken, chatId: tgChat });
      setTgResult(`connected as @${r.bot} · chat ${r.chat_id}`);
      setTgToken("");
      void tg.refresh();
    } catch (e: any) {
      setTgResult(`error: ${e?.message ?? "failed"}`);
    } finally {
      setTgBusy(false);
    }
  };
  const toggleTelegram = async (action: "start" | "stop") => {
    setTgBusy(true);
    try {
      await api.post(`/telegram/${action}`, {});
      void tg.refresh();
    } catch (e: any) {
      setTgResult(`error: ${e?.message ?? "failed"}`);
    } finally {
      setTgBusy(false);
    }
  };
  const sendTelegramPing = async () => {
    try {
      await api.post("/telegram/message", { text: "Pegasus test ping — remote control is live." });
      setTgResult("test message sent");
    } catch (e: any) {
      setTgResult(`error: ${e?.message ?? "failed"}`);
    }
  };

  const recs = useApi<{ models: { id: string; est_gb: number; fits: boolean; tier: string; files?: string[] }[]; platform: string }>("/models/recommended");
  const modelsByHW = (recs.data?.models ?? []).map(m => ({
    label: `${m.id} (${m.est_gb} GB${m.fits ? "" : " — tight"})`,
    id: m.id, fmt: (m.tier ?? "gguf").toUpperCase(), size: `~${m.est_gb} GB`,
  }));
  const installLocal = async () => {
    setDownloading(true);
    try {
      const best = recs.data?.models?.find(m => m.fits) ?? recs.data?.models?.[0];
      if (!best) return;
      await api.post("/models/download", { model: best.id, filename: best.files?.[0] ?? "" });
      await api.post("/models/select", { model: best.id, filename: best.files?.[0] ?? "" });
    } finally {
      setDownloading(false);
    }
  };

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

      <Panel title="AI Provider & Local Model" actions={<Badge tone="ok">v2.1</Badge>}>
        <div className="grid-2" style={{ gap: 10 }}>
          <div className="col">
            <label className="mono tiny">Provider</label>
            <select className="mono tiny" value={provider} onChange={e => setProvider(e.target.value)} style={{ padding: 6, width: "100%" }}>
              <option value="openrouter">OpenRouter (fallback)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="local">Local (GGUF / MLX)</option>
            </select>
            <label className="mono tiny">Model — best for this device</label>
            <select className="mono tiny" value={model} onChange={e => setModel(e.target.value)} style={{ padding: 6, width: "100%" }}>
              {modelsByHW.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
            <label className="mono tiny">Format</label>
            <div className="mono tiny">GGUF (Windows/Linux/Android) · MLX (mac/iOS)</div>
          </div>
          <div className="col">
            <label className="mono tiny">Download local model</label>
            <Button size="sm" onClick={() => void installLocal()} disabled={downloading}>
              {downloading ? "Downloading…" : "Download to workspace"}
            </Button>
            <div className="mono tiny" style={{ marginTop: 6, opacity: 0.8 }}>
              {modelsByHW.find(m => m.id === model)?.fmt} · {modelsByHW.find(m => m.id === model)?.size}
            </div>
            <div className="mono tiny" style={{ marginTop: 6, color: "#ff9e00" }}>
              Set PEGASUS__AI__API_KEY for provider; local runs without network.
            </div>
            <div className="mono tiny" style={{ marginTop: 6 }}>
              <label className="row" style={{ gap: 6, alignItems: "center" }}>
                <input type="checkbox" checked={mimicodeEnabled} onChange={e => setMimicodeEnabled(e.target.checked)} />
                Mimicode / OpenFable / OpenCode integration (settings icon → provider config)
              </label>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Coding agent" id="agents" actions={<Badge tone={(agentAvail as any)?.opencode || (agentAvail as any)?.mimicode ? "ok" : "warn"}>{(agentAvail as any)?.opencode ? "opencode" : (agentAvail as any)?.mimocode ? "mimocode" : "none installed"}</Badge>}>
        <div className="grid-2" style={{ gap: 10 }}>
          <div className="col">
            <label className="mono tiny">Agent receiver</label>
            <select className="mono tiny" value={agentCfg.agent ?? ""} onChange={e => setAgentCfg({ ...agentCfg, agent: e.target.value })} style={{ padding: 6, width: "100%" }}>
              <option value="">—</option>
              <option value="opencode">OpenCode</option>
              <option value="mimocode">Mimicode (OpenFable jailbreak)</option>
            </select>
            <label className="mono tiny">Provider override</label>
            <select className="mono tiny" value={agentCfg.provider ?? ""} onChange={e => setAgentCfg({ ...agentCfg, provider: e.target.value })} style={{ padding: 6, width: "100%" }}>
              <option value="">—</option>
              <option value="openrouter">OpenRouter</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="venice">Venice</option>
              <option value="local">Local model</option>
            </select>
            <label className="mono tiny">Model override</label>
            <input className="mono tiny" value={agentCfg.model ?? ""} onChange={e => setAgentCfg({ ...agentCfg, model: e.target.value })} placeholder="claude-sonnet-4-6" style={{ padding: 6, width: "100%" }} />
          </div>
          <div className="col">
            <label className="mono tiny">Skills directory (.openfable-skills)</label>
            <input className="mono tiny" value={agentCfg.skills ?? ""} onChange={e => setAgentCfg({ ...agentCfg, skills: e.target.value })} placeholder=".openfable-skills" style={{ padding: 6, width: "100%" }} />
            <Button size="sm" onClick={() => void saveAgentCfg()} style={{ marginTop: 8 }}>Save agent config</Button>
            <div className="mono tiny" style={{ marginTop: 6, opacity: 0.8 }}>
              Chat routes through the agent when configured; the NL translator handles everything else.
            </div>
          </div>
        </div>
      </Panel>

      <Panel
        title="Telegram remote control"
        id="telegram"
        actions={<Badge tone={tg.data?.running ? "ok" : tg.data?.configured ? "warn" : "dim"}>{tg.data?.running ? "running" : tg.data?.configured ? "stopped" : "not set"}</Badge>}
      >
        <div className="grid-2" style={{ gap: 10 }}>
          <div className="col">
            <label className="mono tiny">Bot token</label>
            <input
              type="password"
              className="mono tiny"
              style={{ padding: 6, width: "100%", background: "#0d1117", color: "#e6edf3", borderRadius: 6, border: "1px solid rgba(255,255,255,.08)" }}
              placeholder={tg.data?.configured ? "configured ✓" : "123456:ABC-…"}
              value={tgToken}
              onChange={(e) => setTgToken(e.target.value)}
            />
            <label className="mono tiny">Chat ID (blank to auto-discover)</label>
            <input
              className="mono tiny"
              style={{ padding: 6, width: "100%", background: "#0d1117", color: "#e6edf3", borderRadius: 6, border: "1px solid rgba(255,255,255,.08)" }}
              placeholder="message the bot once, then leave blank"
              value={tgChat}
              onChange={(e) => setTgChat(e.target.value)}
            />
          </div>
          <div className="col">
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <Button size="sm" onClick={() => void saveTelegram()} disabled={tgBusy || !tgToken}>
                {tgBusy ? "…" : "Save & connect"}
              </Button>
              {tg.data?.configured && (
                <>
                  <Button size="sm" variant={tg.data?.running ? "ghost" : "primary"} onClick={() => void toggleTelegram(tg.data?.running ? "stop" : "start")}>
                    {tg.data?.running ? "Stop bot" : "Start bot"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => void sendTelegramPing()}>
                    Send test
                  </Button>
                </>
              )}
            </div>
            {tgResult && <div className="mono tiny" style={{ marginTop: 8, opacity: 0.85, wordBreak: "break-all" }}>{tgResult}</div>}
            <div className="mono tiny mute" style={{ marginTop: 8 }}>
              Bot commands: /status /help /shell &lt;cmd&gt; /devices /screenshot — drive the host from anywhere.
            </div>
          </div>
        </div>
      </Panel>

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
