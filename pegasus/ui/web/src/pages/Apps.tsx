import { useMemo, useState } from "react";
import { Boxes, Download, Package, RefreshCw, Search } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { AppRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Stat } from "@/components/ui";
import { initials, titleCase } from "@/lib/format";

export default function Apps() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{ rows: AppRow[] }>("apps", 90000);
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"grid" | "table">("grid");

  const rows = useMemo(() => {
    const list = data?.rows ?? [];
    if (!query.trim()) return list;
    const needle = query.toLowerCase();
    return list.filter(
      (row) =>
        row.name.toLowerCase().includes(needle) ||
        row.packageName.toLowerCase().includes(needle),
    );
  }, [data, query]);

  const groups = useMemo(() => {
    const map = new Map<string, AppRow[]>();
    for (const row of rows) {
      const vendor = row.packageName.split(".").slice(0, 2).join(".");
      map.set(vendor, [...(map.get(vendor) ?? []), row]);
    }
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [rows]);

  return (
    <div className="page">
      <PageHeader
        title="Applications"
        subtitle="Third-party packages installed on the device"
        actions={
          <>
            <Button size="sm" onClick={() => setView(view === "grid" ? "table" : "grid")}>
              {view === "grid" ? "Table view" : "Grid view"}
            </Button>
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Package size={12} /> Pull from device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={data?.rows.length ?? "—"} label="Installed packages" tone="info" />
        <Stat value={groups.length} label="Vendors" />
        <Stat value={rows.length} label="Visible" />
        <Stat value={serial ? "BOUND" : "IDLE"} label="Device" hint={serial ?? "none"} />
      </div>

      <Panel
        title="Installed applications"
        actions={
          <div className="row" style={{ gap: 6 }}>
            <Search size={13} className="mute" />
            <input className="input" style={{ width: 220 }} placeholder="filter package or name" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
        }
      >
        {!serial ? (
          <Empty icon={<Boxes size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <Loading label="Enumerating packages…" rows={6} />
        ) : rows.length === 0 ? (
          <Empty icon={<Boxes size={16} />} title="No packages cached" detail="Pull from device to run pm list packages -3." action={<Button size="sm" variant="primary" onClick={() => void collect()}>Collect now</Button>} />
        ) : view === "grid" ? (
          <div className="grid-3">
            {rows.map((row) => (
              <div className="cmd-card" key={row.packageName} style={{ cursor: "default" }}>
                <div className="row" style={{ gap: 10 }}>
                  <div className="avatar">{initials(row.name)}</div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="td-strong td-truncate">{titleCase(row.name)}</div>
                    <div className="tiny mono mute td-truncate">{row.packageName}</div>
                  </div>
                  {row.version ? <Badge tone="dim">v{row.version}</Badge> : null}
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="tiny mute td-truncate" style={{ maxWidth: 160 }}>{row.path}</span>
                  <Button size="xs" variant="ghost" title="Package details">
                    <Download size={11} />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Package</th><th>Name</th><th>Version</th><th>APK path</th></tr></thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.packageName}>
                    <td className="mono tiny td-strong">{row.packageName}</td>
                    <td>{titleCase(row.name)}</td>
                    <td className="mono tiny">{row.version || "—"}</td>
                    <td className="mono tiny td-truncate" style={{ maxWidth: 380 }}>{row.path}</td>
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
