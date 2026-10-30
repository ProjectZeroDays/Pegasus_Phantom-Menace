import { useMemo, useState } from "react";
import { MessageSquare, RefreshCw, Search, Send } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { SmsRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

export default function Messages() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: SmsRow[] }>("sms", 45000);
  const [filter, setFilter] = useState<"all" | "incoming" | "outgoing" | "unread">("all");
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    let list = data?.rows ?? [];
    if (filter === "incoming") list = list.filter((row) => row.direction === "incoming");
    if (filter === "outgoing") list = list.filter((row) => row.direction === "outgoing");
    if (filter === "unread") list = list.filter((row) => !row.read);
    if (query.trim()) {
      const needle = query.toLowerCase();
      list = list.filter(
        (row) => row.address.toLowerCase().includes(needle) || row.body.toLowerCase().includes(needle),
      );
    }
    return list;
  }, [data, filter, query]);

  const stats = useMemo(() => {
    const list = data?.rows ?? [];
    return {
      total: list.length,
      incoming: list.filter((r) => r.direction === "incoming").length,
      unread: list.filter((r) => !r.read).length,
      threads: new Set(list.map((r) => r.address)).size,
    };
  }, [data]);

  return (
    <div className="page">
      <PageHeader
        title="Messages"
        subtitle="SMS inbox and outbox from content://sms"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Send size={12} /> Pull from device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={stats.total} label="Messages" tone="info" />
        <Stat value={stats.threads} label="Threads" />
        <Stat value={stats.incoming} label="Inbound" tone="ok" />
        <Stat value={stats.unread} label="Unread" tone={stats.unread ? "warn" : undefined} />
      </div>

      <Panel
        title="Message stream"
        actions={
          <>
            <Segmented
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All" },
                { value: "incoming", label: "Inbound" },
                { value: "outgoing", label: "Outbound" },
                { value: "unread", label: "Unread" },
              ]}
            />
            <div className="row" style={{ gap: 6 }}>
              <Search size={13} className="mute" />
              <input className="input" style={{ width: 200 }} placeholder="search sender / body" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
          </>
        }
      >
        {!serial ? (
          <Empty icon={<MessageSquare size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <Loading label="Reading SMS provider…" rows={5} />
        ) : rows.length === 0 ? (
          <Empty icon={<MessageSquare size={16} />} title="No messages" detail="Pull from device to read the SMS store." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : (
          <div className="col" style={{ gap: 8 }}>
            {rows.map((row) => (
              <div
                key={row.id}
                style={{
                  border: "1px solid var(--line-soft)",
                  borderRadius: 7,
                  padding: "10px 12px",
                  background: row.direction === "incoming" ? "rgba(88,166,255,.04)" : "rgba(255,61,0,.04)",
                }}
              >
                <div className="row" style={{ justifyContent: "space-between", marginBottom: 5 }}>
                  <span className="row" style={{ gap: 8 }}>
                    <span className="mono tiny strong">{row.address}</span>
                    <Badge tone={row.direction === "incoming" ? "info" : "primary"}>{row.direction}</Badge>
                    {!row.read && <Badge tone="warn">unread</Badge>}
                  </span>
                  <span className="tiny mute">{formatDateTime(row.sentAt)}</span>
                </div>
                <div className="small" style={{ lineHeight: 1.6 }}>{row.body || "(empty body)"}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
