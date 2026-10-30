import { useMemo, useState } from "react";
import { RefreshCw, Router, Search, ShieldCheck, Signal, Wifi } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { WifiRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Stat } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

export default function WifiNetworks() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: WifiRow[] }>("wifi", 60000);
  const [query, setQuery] = useState("");

  const rows = useMemo(() => {
    const list = data?.rows ?? [];
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter(
      (row) => row.ssid.toLowerCase().includes(needle) || (row.bssid ?? "").toLowerCase().includes(needle),
    );
  }, [data, query]);

  const connected = (data?.rows ?? []).filter((row) => row.isConnected).length;

  return (
    <div className="page">
      <PageHeader
        title="Wi-Fi Networks"
        subtitle="Known networks and scan results from dumpsys wifi"
        actions={
          <>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Wifi size={12} /> Scan device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.rows.length ?? "—"} label="Networks seen" tone="info" />
        <Stat value={connected} label="Connected" tone={connected ? "ok" : "warn"} />
        <Stat value={rows.length} label="Visible after filter" />
        <Stat value={serial ? "BOUND" : "IDLE"} label="Device" hint={serial ?? "none"} />
      </div>

      <Panel
        title="Network inventory"
        tight
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 220 }} placeholder="filter ssid / bssid" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<Wifi size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <div style={{ padding: 16 }}><Loading label="Reading wifi service…" /></div>
        ) : rows.length === 0 ? (
          <Empty icon={<Wifi size={16} />} title="No networks cached" detail="Collect to read configured and visible networks." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>SSID</th><th>BSSID</th><th>State</th><th>Security</th><th>Last seen</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.id}-${row.ssid}`}>
                    <td>
                      <span className="row" style={{ gap: 8 }}>
                        {row.isConnected ? <Signal size={13} className="orange" /> : <Wifi size={13} className="mute" />}
                        <span className="td-strong td-truncate">{row.ssid || "(hidden)"}</span>
                      </span>
                    </td>
                    <td className="mono tiny">{row.bssid ?? "—"}</td>
                    <td><Badge tone={row.isConnected ? "ok" : "dim"} dot>{row.isConnected ? "connected" : "known"}</Badge></td>
                    <td><span className="badge badge-dim"><ShieldCheck size={9} />{row.isConnected ? "wpa2/3" : "wpa"}</span></td>
                    <td className="tiny mute">{row.lastSeenAt ? formatDateTime(row.lastSeenAt) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel title="Interfaces" muted>
        <div className="grid-3">
          {[
            { icon: <Wifi size={13} />, label: "wlan0", detail: "primary Wi-Fi interface" },
            { icon: <Router size={13} />, label: "gateway", detail: "default route discovery" },
            { icon: <Signal size={13} />, label: "scan results", detail: "cmd wifi list-scan-results" },
          ].map((item) => (
            <div className="cmd-card" key={item.label} style={{ cursor: "default", flexDirection: "row", alignItems: "center" }}>
              {item.icon}
              <div>
                <div className="small">{item.label}</div>
                <div className="tiny mute">{item.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
