import { useMemo, useState } from "react";
import { Phone, PhoneIncoming, PhoneMissed, PhoneOutgoing, RefreshCw, Search } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { CallRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Progress, Segmented, Stat } from "@/components/ui";
import { formatDateTime, formatDuration } from "@/lib/format";

export default function Calls() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: CallRow[] }>("calls", 45000);
  const [filter, setFilter] = useState<"all" | "incoming" | "outgoing" | "missed">("all");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    let list = data?.rows ?? [];
    if (filter !== "all") list = list.filter((row) => row.callType === filter);
    if (query.trim()) {
      const needle = query.toLowerCase();
      list = list.filter(
        (row) =>
          row.name.toLowerCase().includes(needle) || row.phone.toLowerCase().includes(needle),
      );
    }
    return list;
  }, [data, filter, query]);

  const stats = useMemo(() => {
    const list = data?.rows ?? [];
    const totalSeconds = list.reduce((acc, row) => acc + row.durationSeconds, 0);
    return {
      total: list.length,
      incoming: list.filter((r) => r.callType === "incoming").length,
      outgoing: list.filter((r) => r.callType === "outgoing").length,
      missed: list.filter((r) => r.callType === "missed").length,
      talk: totalSeconds,
    };
  }, [data]);

  return (
    <div className="page">
      <PageHeader
        title="Call Logs"
        subtitle="Inbound, outbound and missed call history"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Phone size={12} /> Pull from device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={stats.total} label="Total records" tone="info" />
        <Stat value={stats.incoming} label="Incoming" tone="ok" />
        <Stat value={stats.outgoing} label="Outgoing" />
        <Stat value={formatDuration(stats.talk)} label="Total talk time" hint={`${stats.missed} missed`} tone="warn" />
      </div>

      <Panel
        title="Call history"
        tight
        actions={
          <>
            <Segmented
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All" },
                { value: "incoming", label: "In" },
                { value: "outgoing", label: "Out" },
                { value: "missed", label: "Missed" },
              ]}
            />
            <div className="row" style={{ gap: 6 }}>
              <Search size={13} className="mute" />
              <input className="input" style={{ width: 180 }} placeholder="search name / number" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
          </>
        }
      >
        {!serial ? (
          <Empty icon={<Phone size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <div style={{ padding: 16 }}><Loading label="Reading call log provider…" /></div>
        ) : rows.length === 0 ? (
          <Empty icon={<Phone size={16} />} title="No call records" detail="Pull from device to read content://call_log/calls." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>Direction</th><th>Contact</th><th>Number</th><th>Duration</th><th>When</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Badge tone={row.callType === "missed" ? "err" : row.callType === "incoming" ? "ok" : "info"}>
                        {row.callType === "incoming" ? <PhoneIncoming size={10} /> : row.callType === "outgoing" ? <PhoneOutgoing size={10} /> : <PhoneMissed size={10} />}
                        {row.callType}
                      </Badge>
                    </td>
                    <td className="td-strong td-truncate">{row.name || "Unknown"}</td>
                    <td className="mono tiny">{row.phone}</td>
                    <td>
                      <div className="meter" style={{ width: 120 }}>
                        <Progress value={Math.min(100, (row.durationSeconds / 300) * 100)} thin />
                        <span className="tiny mono">{formatDuration(row.durationSeconds)}</span>
                      </div>
                    </td>
                    <td className="tiny mute">{formatDateTime(row.calledAt)}</td>
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
