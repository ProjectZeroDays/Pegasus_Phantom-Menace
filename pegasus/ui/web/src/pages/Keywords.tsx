import { useMemo, useState } from "react";
import { AlertTriangle, KeyRound, Plus, RefreshCw, Scan, Trash2 } from "lucide-react";
import { api, useApi } from "@/lib/api";
import type { Keyword, KeywordHit } from "@/lib/types";
import { useApp } from "@/state/AppContext";
import { Badge, Button, Empty, Field, PageHeader, Panel, Stat } from "@/components/ui";
import { formatDateTime, timeAgo } from "@/lib/format";

export default function Keywords() {
  const { activeSerial } = useApp();
  const [keyword, setKeyword] = useState("");
  const [hits, setHits] = useState<KeywordHit[] | null>(null);
  const [scanning, setScanning] = useState(false);

  const path = activeSerial ? `/devices/${encodeURIComponent(activeSerial)}/keywords` : null;
  const { data, loading, refresh } = useApi<{ keywords: Keyword[] }>(path, { deps: [activeSerial] });

  const add = async () => {
    if (!activeSerial || !keyword.trim()) return;
    await api.post(`/devices/${encodeURIComponent(activeSerial)}/keywords`, { keyword: keyword.trim() });
    setKeyword("");
    refresh();
  };

  const scan = async () => {
    if (!activeSerial) return;
    setScanning(true);
    try {
      const result = await api.post<{ hits: KeywordHit[]; matched: number }>(
        `/devices/${encodeURIComponent(activeSerial)}/keywords/scan`,
      );
      setHits(result.hits);
      refresh();
    } finally {
      setScanning(false);
    }
  };

  const keywords = data?.keywords ?? [];
  const totalHits = useMemo(
    () => keywords.reduce((acc, row) => acc + row.hitCount, 0),
    [keywords],
  );

  return (
    <div className="page">
      <PageHeader
        title="Keyword Tracking"
        subtitle="Match keywords across SMS, call logs and browser titles"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void scan()} disabled={!activeSerial || scanning}>
              <Scan size={12} /> {scanning ? "Scanning…" : "Scan corpus"}
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={keywords.length} label="Tracked keywords" tone="info" />
        <Stat value={totalHits} label="Total hits" tone={totalHits ? "warn" : undefined} />
        <Stat value={hits?.filter((hit) => hit.matchCount > 0).length ?? "—"} label="Matched on last scan" />
        <Stat value={activeSerial ? "BOUND" : "IDLE"} label="Device" hint={activeSerial ?? "none"} />
      </div>

      <Panel title="Add keyword">
        <div className="form-row">
          <Field label="Keyword or phrase">
            <input
              className="input"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void add()}
              placeholder="e.g. bank, password, OTP"
            />
          </Field>
          <Field label="Action">
            <button className="btn btn-primary" disabled={!activeSerial || !keyword.trim()} onClick={() => void add()}>
              <Plus size={13} /> Track keyword
            </button>
          </Field>
        </div>
      </Panel>

      <Panel title="Tracked keywords" tight>
        {!activeSerial ? (
          <Empty icon={<KeyRound size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <div style={{ padding: 16 }} className="tiny mute">Loading keywords…</div>
        ) : keywords.length === 0 ? (
          <Empty icon={<KeyRound size={16} />} title="No keywords tracked" detail="Add a keyword above to start monitoring." />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Keyword</th><th>Hits</th><th>Last hit</th><th>Created</th><th /></tr></thead>
              <tbody>
                {keywords.map((row) => (
                  <tr key={row.id}>
                    <td className="td-strong">{row.keyword}</td>
                    <td><Badge tone={row.hitCount ? "warn" : "dim"}>{row.hitCount}</Badge></td>
                    <td className="tiny mute">{row.lastHitAt ? timeAgo(row.lastHitAt) : "—"}</td>
                    <td className="tiny mute">{formatDateTime(row.createdAt)}</td>
                    <td>
                      <Button
                        size="xs"
                        variant="danger"
                        onClick={async () => { await api.del(`/keywords/${row.id}`); refresh(); }}
                      >
                        <Trash2 size={11} />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {hits && (
        <Panel title="Scan results" actions={<Badge tone="dim">{hits.reduce((acc, hit) => acc + hit.matchCount, 0)} matches</Badge>}>
          {hits.length === 0 ? (
            <Empty title="Nothing scanned" detail="Add at least one keyword first." />
          ) : (
            <div className="col" style={{ gap: 10 }}>
              {hits.map((hit) => (
                <div key={hit.id} className="cmd-card" style={{ cursor: "default" }}>
                  <div className="cmd-name">
                    <span>{hit.keyword}</span>
                    <Badge tone={hit.matchCount ? "warn" : "dim"}>{hit.matchCount} hits</Badge>
                  </div>
                  {hit.matches.length === 0 ? (
                    <div className="tiny mute">no matches in the collected corpus</div>
                  ) : (
                    <div className="col" style={{ gap: 4 }}>
                      {hit.matches.slice(0, 6).map((match, index) => (
                        <div className="row tiny" key={index} style={{ gap: 8 }}>
                          <AlertTriangle size={10} className="yellow" />
                          <span className="mute" style={{ width: 90 }}>{match.source}</span>
                          <span className="td-truncate" style={{ maxWidth: 480 }}>{match.text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
