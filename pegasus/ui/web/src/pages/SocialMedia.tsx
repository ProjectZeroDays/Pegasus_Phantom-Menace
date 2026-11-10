import { useState } from "react";
import { Globe, Plus, Radio, RefreshCw, Share2, Shield } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface Platform {
  id: string;
  name: string;
  status: string;
  osint: string[];
}

interface Campaign {
  id: string;
  name: string;
  platforms: string[];
  keywords: string[];
  status: string;
  created_at: number;
  collected_intel: number;
}

interface IntelItem {
  id: string;
  ts: number;
  platform: string;
  actor: string;
  text: string;
  tags: string[];
  severity: string;
}

interface SocialStatus {
  platforms_supported: number;
  campaigns: number;
  active_campaigns: number;
  intel_items: number;
  store: string;
  mode: string;
}

const SEV: Record<string, "err" | "warn" | "info" | "ok" | "dim"> = {
  critical: "err",
  high: "err",
  medium: "warn",
  low: "info",
  info: "dim",
};

export default function SocialMedia() {
  const [name, setName] = useState("");
  const [platforms, setPlatforms] = useState("reddit,github");
  const [keywords, setKeywords] = useState("credential,dump");
  const [busy, setBusy] = useState(false);

  const status = useApi<SocialStatus>("/social-media/status", { interval: 30000 });
  const platformsRes = useApi<{ platforms: Platform[] }>("/social-media/platforms");
  const campaignsRes = useApi<{ campaigns: Campaign[] }>("/social-media/campaigns");
  const intelRes = useApi<{ intel: IntelItem[] }>("/social-media/intel");

  const campaigns = campaignsRes.data?.campaigns ?? [];
  const intel = intelRes.data?.intel ?? [];
  const catalog = platformsRes.data?.platforms ?? [];

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.post("/social-media/campaigns", {
        name: name.trim(),
        platforms: platforms.split(",").map((s) => s.trim()).filter(Boolean),
        keywords: keywords.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setName("");
      campaignsRes.refresh();
      status.refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Social Media Intelligence"
        subtitle="OSINT collection surfaces for threat intel and campaign tracking — manual/authorized collection only"
        actions={<Button size="sm" onClick={() => { campaignsRes.refresh(); intelRes.refresh(); status.refresh(); }}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={catalog.length} label="Platform catalog" tone="info" />
        <Stat value={campaigns.length} label="Campaigns" tone="warn" />
        <Stat value={status.data?.active_campaigns ?? "—"} label="Active" tone="ok" />
        <Stat value={intel.length} label="Intel items" tone="warn" />
      </div>

      <Panel title="New collection campaign">
        <div className="form-row">
          <Field label="Campaign name">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme leak monitoring" />
          </Field>
          <Field label="Platforms (comma separated)">
            <input className="input" value={platforms} onChange={(e) => setPlatforms(e.target.value)} placeholder="reddit,github,twitter" />
          </Field>
          <Field label="Keywords (comma separated)">
            <input className="input" value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="credential,dump,combolist" />
          </Field>
          <Field label="Create">
            <button className="btn btn-primary" onClick={() => void create()} disabled={busy || !name.trim()}>
              <Plus size={13} /> Create
            </button>
          </Field>
        </div>
        <p className="tiny mute">Mode: <code>{status.data?.mode ?? "loading…"}</code>. No scraping is performed without an operator decision; intel store: {status.data?.store ?? "—"}</p>
      </Panel>

      <Panel title="Platform catalog" tight>
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>Platform</th><th>ID</th><th>Available OSINT surfaces</th></tr></thead>
            <tbody>
              {catalog.map((p) => (
                <tr key={p.id}>
                  <td className="td-strong"><Globe size={11} style={{ display: "inline" }} /> {p.name}</td>
                  <td className="mono tiny">{p.id}</td>
                  <td className="tiny">{p.osint.join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Active campaigns" tight>
        {campaigns.length === 0 ? (
          <Empty icon={<Share2 size={16} />} title="No campaigns" detail="Create one above to begin tracking." action={<Button size="sm" variant="primary" onClick={() => void create()}>Create</Button>} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Campaign</th><th>Platforms</th><th>Status</th><th>Intel</th><th>Created</th></tr></thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id}>
                    <td className="td-strong td-truncate">{c.name}</td>
                    <td className="tiny mono">{c.platforms.join(", ")}</td>
                    <td><Badge tone={c.status === "active" ? "ok" : "dim"}>{c.status}</Badge></td>
                    <td className="mono tiny">{c.collected_intel}</td>
                    <td className="tiny mute">{new Date(c.created_at * 1000).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Intelligence feed" tight>
        {intel.length === 0 ? (
          <Empty icon={<Shield size={16} />} title="No intel collected" detail="POST /api/social-media/intel to log findings, or wire a collector into your workflow." action={<Radio size={14} />} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Severity</th><th>Platform</th><th>Summary</th><th>When</th></tr></thead>
              <tbody>
                {intel.slice(-25).reverse().map((item) => (
                  <tr key={item.id}>
                    <td><Badge tone={SEV[item.severity] ?? "dim"}>{item.severity}</Badge></td>
                    <td className="tiny mono">{item.platform}</td>
                    <td className="td-truncate tiny">{item.text}</td>
                    <td className="tiny mute">{new Date(item.ts * 1000).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
