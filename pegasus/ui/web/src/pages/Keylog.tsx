import { useMemo, useState } from "react";
import { Keyboard, RefreshCw, Search } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { KeylogRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Stat, Terminal } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

export default function Keylog() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: KeylogRow[] }>("keylog", 30000);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const list = data?.rows ?? [];
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter((row) => row.text.toLowerCase().includes(needle) || row.app.toLowerCase().includes(needle));
  }, [data, query]);

  return (
    <div className="page">
      <PageHeader
        title="Keystrokes"
        subtitle="Input event queue captured from dumpsys input"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Keyboard size={12} /> Capture queue
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={rows.length} label="Events captured" tone="info" />
        <Stat value={new Set((data?.rows ?? []).map((row) => row.app)).size} label="Sources" />
        <Stat value="system" label="Input owner" hint="dumpsys input" />
        <Stat value={serial ? "LIVE" : "IDLE"} label="Device" hint={serial ?? "none"} tone={serial ? "ok" : undefined} />
      </div>

      <Panel
        title="Input stream"
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 220 }} placeholder="filter event text" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<Keyboard size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <Loading label="Reading input queue…" rows={5} />
        ) : rows.length === 0 ? (
          <Empty icon={<Keyboard size={16} />} title="No keystrokes buffered" detail="Capture the input queue to populate this stream." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Capture now</Button>} />
        ) : (
          <>
            <Terminal
              lines={rows.map((row) => ({ text: `[${new Date(row.recordedAt).toLocaleTimeString()}] ${row.app} :: ${row.text}` }))}
              title="input queue"
              maxHeight={360}
            />
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="tbl">
                <thead><tr><th>#</th><th>Source</th><th>Event</th><th>Recorded</th></tr></thead>
                <tbody>
                  {rows.slice(0, 60).map((row) => (
                    <tr key={row.id}>
                      <td className="mono tiny mute">{row.id}</td>
                      <td><Badge tone="dim">{row.app}</Badge></td>
                      <td className="mono tiny td-truncate" style={{ maxWidth: 520 }}>{row.text}</td>
                      <td className="tiny mute">{formatDateTime(row.recordedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
