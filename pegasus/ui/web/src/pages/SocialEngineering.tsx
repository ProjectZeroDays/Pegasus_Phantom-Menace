import { useState } from "react";
import { Fish, GraduationCap, Mail, Plus, RefreshCw, ShieldCheck, Target } from "lucide-react";
import { api, useApi } from "@/lib/api";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";

interface Template {
  id: string;
  name: string;
  channel: string;
  difficulty: string;
}

interface AwarenessModule {
  id: string;
  name: string;
  minutes: number;
  audience: string;
}

interface Campaign {
  id: string;
  name: string;
  template_id: string;
  channel: string;
  audience: string;
  status: string;
  created_at: number;
  sent: number;
  clicked: number;
}

interface SeStatus {
  templates: number;
  awareness_modules: number;
  campaigns: number;
  messages_sent: number;
  click_rate: number;
  mode: string;
}

export default function SocialEngineering() {
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("t-mfa-reset");
  const [channel, setChannel] = useState("email");
  const [audience, setAudience] = useState("all-hands");
  const [busy, setBusy] = useState(false);

  const status = useApi<SeStatus>("/se/status", { interval: 60000 });
  const templatesRes = useApi<{ templates: Template[] }>("/se/templates");
  const awarenessRes = useApi<{ modules: AwarenessModule[] }>("/se/awareness");
  const campaignsRes = useApi<{ campaigns: Campaign[] }>("/se/campaigns");

  const templates = templatesRes.data?.templates ?? [];
  const awareness = awarenessRes.data?.modules ?? [];
  const campaigns = campaignsRes.data?.campaigns ?? [];

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.post("/se/campaigns", { name: name.trim(), template_id: templateId, channel, audience });
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
        title="Social Engineering Training"
        subtitle="Authorized simulated-phishing and awareness program management — opt-in targets only"
        actions={<Button size="sm" onClick={() => { campaignsRes.refresh(); status.refresh(); }}><RefreshCw size={12} /> Refresh</Button>}
      />

      <div className="stat-grid">
        <Stat value={templates.length} label="Lure templates" tone="info" />
        <Stat value={awareness.length} label="Awareness modules" tone="ok" />
        <Stat value={campaigns.length} label="Campaigns" tone="warn" />
        <Stat value={status.data ? `${(status.data.click_rate * 100).toFixed(1)}%` : "—"} label="Click rate" tone="warn" />
      </div>

      <Panel title="New simulation campaign (draft)">
        <div className="form-row">
          <Field label="Campaign name">
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Q4 phishing resilience drill" />
          </Field>
          <Field label="Template">
            <select className="input" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </Field>
          <Field label="Channel">
            <select className="input" value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="email">email</option>
              <option value="sms">sms</option>
              <option value="physical">physical</option>
            </select>
          </Field>
          <Field label="Audience">
            <input className="input" value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="all-hands / helpdesk / finance" />
          </Field>
          <Field label="Create">
            <button className="btn btn-primary" onClick={() => void create()} disabled={busy || !name.trim()}>
              <Plus size={13} /> Create
            </button>
          </Field>
        </div>
        <p className="tiny mute">Mode: {status.data?.mode ?? "awareness-training"}. Campaigns are created in <code>draft</code> status — an operator must explicitly activate and launch; nothing sends automatically.</p>
      </Panel>

      <Panel title="Simulation templates" tight>
        {templates.length === 0 ? (
          <Empty icon={<Mail size={16} />} title="Templates unavailable" detail="The SE template catalog failed to load." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Template</th><th>Channel</th><th>Difficulty</th></tr></thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id}>
                    <td className="td-strong"><Mail size={11} style={{ display: "inline" }} /> {t.name}</td>
                    <td className="mono tiny">{t.channel}</td>
                    <td><Badge tone={t.difficulty === "hard" ? "err" : t.difficulty === "medium" ? "warn" : "ok"}>{t.difficulty}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Awareness curriculum" tight>
        {awareness.length === 0 ? (
          <Empty icon={<GraduationCap size={16} />} title="No modules" detail="Awareness modules failed to load." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Module</th><th>Audience</th><th>Length</th></tr></thead>
              <tbody>
                {awareness.map((m) => (
                  <tr key={m.id}>
                    <td className="td-strong"><GraduationCap size={11} style={{ display: "inline" }} /> {m.name}</td>
                    <td className="tiny mono">{m.audience}</td>
                    <td className="tiny mute">{m.minutes} min</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Campaign history" tight>
        {campaigns.length === 0 ? (
          <Empty icon={<Fish size={16} />} title="No campaigns" detail="Create a draft campaign above; activate and launch through your authorized phishing platform." action={<Target size={14} />} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Campaign</th><th>Template</th><th>Status</th><th>Sent</th><th>Clicked</th></tr></thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id}>
                    <td className="td-strong td-truncate">{c.name}</td>
                    <td className="tiny mono">{c.template_id}</td>
                    <td><Badge tone={c.status === "active" ? "ok" : c.status === "completed" ? "info" : "dim"}>{c.status}</Badge></td>
                    <td className="mono tiny">{c.sent}</td>
                    <td className="mono tiny">{c.clicked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Ethics & rules of engagement" tight>
        <ul className="tiny" style={{ margin: 0, paddingLeft: 18 }}>
          <li><ShieldCheck size={11} style={{ display: "inline" }} /> Authorized engagements only; targets are employees of the sponsoring organization, never external individuals.</li>
          <li>Campaigns start in draft; no message is sent without operator activation through the authorized platform.</li>
          <li>Report aggregate metrics only — individual results go to the targeted individual's manager for coaching, never disclosed widely.</li>
          <li><Fish size={11} style={{ display: "inline" }} /> Goal is resilience through training, not gotchas.</li>
        </ul>
      </Panel>
    </div>
  );
}
