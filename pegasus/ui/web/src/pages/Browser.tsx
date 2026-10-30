import { useMemo, useState } from "react";
import { Globe, History, RefreshCw, Search, Star } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { BrowserRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Progress, Stat } from "@/components/ui";
import { formatDateTime, timeAgo } from "@/lib/format";

export default function Browser() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{
    rows: BrowserRow[];
    collectedAt?: number | null;
  }>("browser", 60000);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const list = [...(data?.rows ?? [])].sort((a, b) => b.visitCount - a.visitCount);
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter(
      (row) => row.url.toLowerCase().includes(needle) || row.title.toLowerCase().includes(needle),
    );
  }, [data, query]);

  const top = rows[0];
  const domains = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of data?.rows ?? []) {
      try {
        const host = new URL(row.url).hostname;
        map.set(host, (map.get(host) ?? 0) + 1);
      } catch {
        /* skip malformed urls */
      }
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [data]);

  const maxDomain = domains[0]?.[1] ?? 1;

  return (
    <div className="page">
      <PageHeader
        title="Browser History"
        subtitle="Chrome history database extracted via run-as / root copy"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <History size={12} /> Pull from device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.rows.length ?? "—"} label="History entries" tone="info" />
        <Stat value={domains.length} label="Unique domains" />
        <Stat value={top?.visitCount ?? "—"} label="Top visit count" hint={top?.title ?? "—"} tone="ok" />
        <Stat value={data?.collectedAt ? timeAgo(data.collectedAt * 1000) : "—"} label="Last collection" />
      </div>

      {domains.length > 0 && (
        <Panel title="Domain distribution">
          <div className="col" style={{ gap: 9 }}>
            {domains.map(([domain, count]) => (
              <div className="meter" key={domain}>
                <span className="tiny mono td-truncate" style={{ width: 170 }}>{domain}</span>
                <Progress value={(count / maxDomain) * 100} thin />
                <span className="tiny mono" style={{ width: 32, textAlign: "right" }}>{count}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel
        title="Visited pages"
        tight
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 230 }} placeholder="filter url or title" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<Globe size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <div style={{ padding: 16 }}><Loading label="Extracting Chrome history…" /></div>
        ) : rows.length === 0 ? (
          <Empty icon={<Globe size={16} />} title="No browsing history" detail="Requires Chrome installed and root or debuggable build." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr><th>Title</th><th>URL</th><th>Visits</th><th>Last visited</th></tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="td-strong td-truncate" style={{ maxWidth: 280 }}>{row.title || "(untitled)"}</td>
                    <td className="mono tiny td-truncate" style={{ maxWidth: 380 }}>{row.url}</td>
                    <td>
                      <span className="badge badge-primary"><Star size={9} />{row.visitCount}</span>
                    </td>
                    <td className="tiny mute">{row.lastVisitedAt ? formatDateTime(row.lastVisitedAt) : "—"}</td>
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
