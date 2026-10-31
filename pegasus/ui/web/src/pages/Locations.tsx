import { useMemo, useState } from "react";
import { MapPin, Navigation, RefreshCw, Search } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { LocationRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Stat } from "@/components/ui";
import { formatDateTime, timeAgo } from "@/lib/format";

export default function Locations() {
  const { data, loading, error, refresh, collect, serial, burst } = useTelemetry<{
    rows: LocationRow[];
    collectedAt?: number | null;
  }>("locations", 30000);
  const [query, setQuery] = useState("");
  const [collecting, setCollecting] = useState(false);

  const rows = useMemo(() => {
    const list = data?.rows ?? [];
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter(
      (row) =>
        row.address.toLowerCase().includes(needle) ||
        String(row.lat).includes(needle) ||
        String(row.lng).includes(needle),
    );
  }, [data, query]);

  const bounds = useMemo(() => {
    const list = data?.rows ?? [];
    if (!list.length) return null;
    const lats = list.map((r) => r.lat);
    const lngs = list.map((r) => r.lng);
    return {
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
      minLng: Math.min(...lngs),
      maxLng: Math.max(...lngs),
    };
  }, [data]);

  const doCollect = async () => {
    setCollecting(true);
    try {
      await collect();
      setTimeout(burst, 1200);
    } finally {
      setCollecting(false);
    }
  };

  return (
    <div className="page">
      <PageHeader
        title="Locations"
        subtitle="GPS and fused location history pulled from the device"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void doCollect()} disabled={!serial || collecting}>
              <Navigation size={12} /> {collecting ? "Collecting…" : "Pull from device"}
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.rows.length ?? "—"} label="Location points" hint={data?.collectedAt ? `sampled ${timeAgo(data.collectedAt * 1000)}` : "—"} tone="info" />
        <Stat value={bounds ? `${(bounds.maxLat - bounds.minLat).toFixed(3)}°` : "—"} label="Latitude span" />
        <Stat value={bounds ? `${(bounds.maxLng - bounds.minLng).toFixed(3)}°` : "—"} label="Longitude span" />
        <Stat value={bounds ? `${bounds.minLat.toFixed(2)}, ${bounds.minLng.toFixed(2)}` : "—"} label="Origin corner" />
      </div>

      <Panel
        title="Location history"
        tight
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 220 }} placeholder="filter coordinates or address" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<MapPin size={16} />} title="No device selected" detail="Choose a device in the sidebar." />
        ) : loading && !data ? (
          <div style={{ padding: 16 }}><Loading label="Reading location provider…" /></div>
        ) : error ? (
          <Empty title="Location unavailable" detail={error instanceof Error ? error.message : String(error)} />
        ) : rows.length === 0 ? (
          <Empty icon={<MapPin size={16} />} title="No location samples" detail="Pull from device to populate the buffer." action={<Button size="sm" variant="primary" onClick={() => void doCollect()}>Collect now</Button>} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>#</th><th>Latitude</th><th>Longitude</th><th>Address</th><th>Source</th><th>Recorded</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="mono tiny mute">{row.id}</td>
                    <td className="mono">{row.lat.toFixed(6)}</td>
                    <td className="mono">{row.lng.toFixed(6)}</td>
                    <td className="td-truncate">{row.address}</td>
                    <td><Badge tone="dim">{row.source ?? "gps"}</Badge></td>
                    <td className="tiny mute">{row.recordedAt ? formatDateTime(row.recordedAt) : "—"}</td>
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
