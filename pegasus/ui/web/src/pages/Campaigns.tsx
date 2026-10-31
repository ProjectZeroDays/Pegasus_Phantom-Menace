import { useMemo, useState } from "react";
import { ClipboardList, Plus, RefreshCw, Target } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { CampaignRow } from "@/lib/types";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { formatDateTime, titleCase } from "@/lib/format";

export default function Campaigns() {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", client: "", description: "", authorization: "written" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(null);
  const [channel, setChannel] = useState<string>("sms");
  const [payloadUrl, setPayloadUrl] = useState<string>("");
  const [target, setTarget] = useState<string>("");

  const { data, loading, refresh } = useApi<{
    campaigns: CampaignRow[];
    stats: Record<string, unknown>;
    error?: string;
  }>("/campaigns", { interval: 30000 });

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/campaigns", form);
      setForm({ name: "", client: "", description: "", authorization: "written" });
      setShowForm(false);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const deploy = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/campaigns/deploy", {
        campaign_id: selectedCampaignId,
        channel,
        payload_url: payloadUrl,
        target,
      });
      setTarget("");
      setPayloadUrl("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const campaigns = data?.campaigns ?? [];
  const stats = useMemo(() => {
    const values = Object.values(data?.stats ?? {});
    return {
      totals: values.length,
      compiled: JSON.stringify(data?.stats ?? {}),
    };
  }, [data]);

  return (
    <div className="page">
      <PageHeader
        title="Campaigns"
        subtitle="Assessment grouping with targets, findings and authorization records"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => setShowForm((v) => !v)}>
              <Plus size={12} /> New campaign
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={campaigns.length} label="Campaigns" tone="info" />
        <Stat value={stats.totals} label="Global stats keys" />
        <Stat value={campaigns.filter((c) => (c.status ?? "").toLowerCase() === "active").length} label="Active" tone="ok" />
        <Stat value={campaigns.filter((c) => (c.status ?? "").toLowerCase() === "complete").length} label="Completed" />
      </div>

      {showForm && (
        <Panel title="Create campaign">
          <div className="form-row">
            <Field label="Campaign name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Q4 Android assessment" />
            </Field>
            <Field label="Client">
              <input className="input" value={form.client} onChange={(e) => setForm({ ...form, client: e.target.value })} />
            </Field>
            <Field label="Authorization">
              <select className="select" value={form.authorization} onChange={(e) => setForm({ ...form, authorization: e.target.value })}>
                <option value="written">Written authorization</option>
                <option value="verbal">Verbal authorization</option>
                <option value="internal">Internal / owned</option>
              </select>
            </Field>
            <Field label="Create">
              <button className="btn btn-primary" disabled={busy || !form.name} onClick={() => void create()}>
                {busy ? "Creating…" : "Create campaign"}
              </button>
            </Field>
          </div>
          <Field label="Description">
            <textarea className="textarea" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Scope, rules of engagement, targets…" />
          </Field>
          {error && <div className="small red">{error}</div>}
        </Panel>
      )}

      <Panel title="Campaign register" tight>
        {loading && !data ? (
          <div style={{ padding: 16 }} className="tiny mute">Loading campaigns…</div>
        ) : campaigns.length === 0 ? (
          <Empty
            icon={<ClipboardList size={16} />}
            title="No campaigns recorded"
            detail={data?.error ?? "Create a campaign to group targets, findings and reports."}
            action={<Button size="sm" variant="primary" onClick={() => setShowForm(true)}>New campaign</Button>}
          />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Campaign</th><th>Client</th><th>Status</th><th>Authorization</th><th>Created</th><th>Targets</th></tr></thead>
              <tbody>
                {campaigns.map((row) => (
                  <tr key={row.campaign_id ?? row.name}>
                    <td className="td-strong td-truncate">{row.name ?? "—"}</td>
                    <td className="tiny">{row.client || "—"}</td>
                    <td><Badge tone={(row.status ?? "").toLowerCase() === "active" ? "ok" : "dim"}>{titleCase(row.status ?? "draft")}</Badge></td>
                    <td><span className="badge badge-info"><Target size={9} />{String((row as Record<string, unknown>).authorization_level ?? "written")}</span></td>
                    <td className="tiny mute">{row.created_at ? formatDateTime(row.created_at) : "—"}</td>
                    <td className="tiny mono">{String((row as Record<string, unknown>).target_count ?? "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Global campaign statistics" muted>
        <pre
          className="tiny"
          style={{
            background: "#0b0e13",
            border: "1px solid var(--line-soft)",
            borderRadius: 6,
            padding: 12,
            maxHeight: 260,
            overflow: "auto",
            margin: 0,
          }}
        >
          {JSON.stringify(data?.stats ?? {}, null, 2)}
        </pre>
      </Panel>

      <div className="grid-2">
        <Panel title="Deploy workflow">
          <div className="form-row">
            <Field label="Campaign">
              <select className="select" value={selectedCampaignId ?? ""} onChange={(e) => setSelectedCampaignId(e.target.value)} style={{ flex: "0 0 180px" }}>
                <option value="">— select —</option>
                {campaigns.map((c) => (
                  <option key={c.campaign_id ?? c.name} value={c.campaign_id ?? c.name}>{c.name ?? "—"}</option>
                ))}
              </select>
            </Field>
            <Field label="Channel">
              <select className="select" value={channel} onChange={(e) => setChannel(e.target.value)} style={{ flex: "0 0 140px" }}>
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="telegram">Telegram</option>
                <option value="signal">Signal</option>
                <option value="facebook">Facebook Messenger</option>
                <option value="email">Email / IP:port</option>
                <option value="bluetooth">Bluetooth</option>
              </select>
            </Field>
            <Field label="Payload URL">
              <input className="input" value={payloadUrl} onChange={(e) => setPayloadUrl(e.target.value)} placeholder="http://ip:port/file.apk" style={{ flex: "0 1 320px" }} />
            </Field>
            <Field label="Target">
              <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="phone number / jid / email" style={{ flex: "0 1 200px" }} />
            </Field>
            <Field label="Deploy">
              <button
                className="btn btn-primary"
                disabled={busy || !selectedCampaignId || !payloadUrl || !target || !channel}
                onClick={() => void deploy()}
              >
                {busy ? "Deploying…" : "Deploy payload"}
              </button>
            </Field>
          </div>
        </Panel>

        <Panel title="Attribution summary">
          <div className="col" style={{ gap: 6 }}>
            <Stat value={campaigns.filter((c) => (c.status ?? "").toLowerCase() === "active").length} label="Active campaigns" tone="ok" />
            <Stat value={campaigns.filter((c) => (c.status ?? "").toLowerCase() === "complete").length} label="Completed" tone="info" />
            <Stat value={campaigns.length} label="Total campaigns" tone="info" />
            <div className="kv" style={{ fontSize: "0.75rem" }}>
              <span className="kv-k row"><ClipboardList size={9} />Total targets:{String(campaigns.reduce((a, c) => a + Number(c.target_count ?? 0), 0))}</span>
              <span className="kv-v mono tiny">finding records:[20]</span>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
