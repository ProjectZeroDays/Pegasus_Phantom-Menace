import { useState } from "react";
import { MapPin, Plus, Power, Radar, Trash2 } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Geofence } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

export default function Geofences() {
  const { activeSerial } = useApp();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: "", lat: "", lng: "", radiusMeters: "500" });
  const [busy, setBusy] = useState(false);

  const path = activeSerial ? `/devices/${encodeURIComponent(activeSerial)}/geofences` : null;
  const { data, loading, refresh } = useApi<{ geofences: Geofence[] }>(path, { deps: [activeSerial] });

  const create = async () => {
    if (!activeSerial) return;
    setBusy(true);
    try {
      await api.post(`/devices/${encodeURIComponent(activeSerial)}/geofences`, {
        name: form.name,
        lat: Number(form.lat),
        lng: Number(form.lng),
        radiusMeters: Number(form.radiusMeters),
      });
      setForm({ name: "", lat: "", lng: "", radiusMeters: "500" });
      setShowForm(false);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const fences = data?.geofences ?? [];
  const active = fences.filter((fence) => fence.isActive).length;

  return (
    <div className="page">
      <PageHeader
        title="Geofences"
        subtitle="Perimeter definitions with breach tracking"
        actions={
          <Button size="sm" variant="primary" onClick={() => setShowForm((v) => !v)} disabled={!activeSerial}>
            <Plus size={13} /> New zone
          </Button>
        }
      />

      <div className="stat-grid">
        <Stat value={fences.length} label="Zones defined" tone="info" />
        <Stat value={active} label="Active zones" tone={active ? "ok" : "warn"} />
        <Stat value={fences.reduce((acc, f) => Math.max(acc, f.radiusMeters), 0) || "—"} label="Largest radius (m)" />
        <Stat value={activeSerial ? "BOUND" : "IDLE"} label="Device" hint={activeSerial ?? "select a device"} />
      </div>

      {showForm && (
        <Panel title="Define perimeter">
          <div className="form-row">
            <Field label="Zone name">
              <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Home, Office, School" />
            </Field>
            <Field label="Latitude">
              <input className="input" type="number" step="any" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} placeholder="37.33182" />
            </Field>
            <Field label="Longitude">
              <input className="input" type="number" step="any" value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} placeholder="-122.03118" />
            </Field>
            <Field label="Radius (m)">
              <input className="input" type="number" value={form.radiusMeters} onChange={(e) => setForm({ ...form, radiusMeters: e.target.value })} />
            </Field>
            <Field label="Deploy">
              <button className="btn btn-primary" disabled={busy || !form.name} onClick={() => void create()}>
                {busy ? "Deploying…" : "Deploy zone"}
              </button>
            </Field>
          </div>
        </Panel>
      )}

      {!activeSerial ? (
        <Panel title="Zones">
          <Empty icon={<Radar size={16} />} title="No device selected" detail="Pick a device to manage its zones." />
        </Panel>
      ) : loading && !data ? (
        <Panel title="Zones"><Empty title="Loading zones…" /></Panel>
      ) : fences.length === 0 ? (
        <Panel title="Zones">
          <Empty icon={<MapPin size={16} />} title="No geofences yet" detail="Create a perimeter to start tracking entries." action={<Button size="sm" variant="primary" onClick={() => setShowForm(true)}>New zone</Button>} />
        </Panel>
      ) : (
        <div className="grid-2">
          {fences.map((fence) => (
            <Panel key={fence.id} title={fence.name} actions={
              <>
                <Button
                  size="xs"
                  onClick={async () => { await api.patch(`/geofences/${fence.id}/toggle`); refresh(); }}
                  title="Toggle active"
                >
                  <Power size={11} /> {fence.isActive ? "disable" : "enable"}
                </Button>
                <Button
                  size="xs"
                  variant="danger"
                  onClick={async () => { await api.del(`/geofences/${fence.id}`); refresh(); }}
                >
                  <Trash2 size={11} />
                </Button>
              </>
            }>
              <div className="kv"><span className="kv-k">Latitude</span><span className="kv-v mono">{fence.lat.toFixed(5)}</span></div>
              <div className="kv"><span className="kv-k">Longitude</span><span className="kv-v mono">{fence.lng.toFixed(5)}</span></div>
              <div className="kv"><span className="kv-k">Radius</span><span className="kv-v">{fence.radiusMeters} m</span></div>
              <div className="kv"><span className="kv-k">Status</span><span className="kv-v"><Badge tone={fence.isActive ? "ok" : "dim"} dot>{fence.isActive ? "active" : "paused"}</Badge></span></div>
              <div className="kv"><span className="kv-k">Created</span><span className="kv-v tiny">{formatDateTime(fence.createdAt)}</span></div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
