import { useMemo, useState } from "react";
import { Activity, Clock, RefreshCw } from "lucide-react";
import { useApi } from "@/lib/api";
import { useTelemetry } from "@/lib/useTelemetry";
import type { ActivityRow, EventRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Progress, Segmented, Stat } from "@/components/ui";
import { formatDateTime, formatDuration, timeAgo, titleCase } from "@/lib/format";

export default function ActivityTimeline() {
  const [tab, setTab] = useState<"apps" | "platform">("apps");
  const telemetry = useTelemetry<{ rows: ActivityRow[] }>("activity", 60000);
  const events = useApi<{ events: EventRow[] }>("/activity?limit=120", { interval: 15000 });

  const appRows = useMemo(() => {
    const list = telemetry.data?.rows ?? [];
    const map = new Map<string, number>();
    for (const row of list) {
      map.set(row.app, (map.get(row.app) ?? 0) + row.durationSeconds);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]);
  }, [telemetry.data]);

  const max = appRows[0]?.[1] ?? 1;
  const totalSeconds = appRows.reduce((acc, [, value]) => acc + value, 0);

  return (
    <div className="page">
      <PageHeader
        title="Activity Timeline"
        subtitle="Foreground app usage plus the platform event log"
        actions={
          <>
            <Segmented
              value={tab}
              onChange={setTab}
              options={[
                { value: "apps", label: "App usage", icon: <Activity size={12} /> },
                { value: "platform", label: "Platform events", icon: <Clock size={12} /> },
              ]}
            />
            <Button size="sm" onClick={() => { events.refresh(); telemetry.refresh(); }}>
              <RefreshCw size={12} /> Refresh
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={appRows.length} label="Tracked packages" tone="info" />
        <Stat value={formatDuration(totalSeconds)} label="Aggregate usage" />
        <Stat value={events.data?.events.length ?? "—"} label="Platform events" />
        <Stat value={events.data?.events[0] ? timeAgo(Number(events.data.events[0].at) * 1000) : "—"} label="Latest event" />
      </div>

      {tab === "apps" ? (
        <Panel
          title="Foreground usage"
          actions={
            <Button size="sm" variant="primary" onClick={() => void telemetry.collect()} disabled={!telemetry.serial}>
              Collect usage
            </Button>
          }
        >
          {!telemetry.serial ? (
            <Empty title="No device selected" detail="Pick a device in the sidebar." />
          ) : telemetry.loading && !telemetry.data ? (
            <Loading label="Reading usagestats…" rows={5} />
          ) : appRows.length === 0 ? (
            <Empty icon={<Activity size={16} />} title="No usage data" detail="Collect usagestats from the device." action={<Button size="sm" variant="primary" onClick={() => void telemetry.collect()}>Collect now</Button>} />
          ) : (
            <div className="col" style={{ gap: 10 }}>
              {appRows.map(([app, seconds]) => (
                <div className="meter" key={app}>
                  <span className="tiny mono td-truncate" style={{ width: 190 }}>{app}</span>
                  <Progress value={(seconds / max) * 100} thin />
                  <span className="tiny mono" style={{ width: 60, textAlign: "right" }}>{formatDuration(seconds)}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      ) : (
        <Panel title="Platform events" tight>
          {!events.data?.events.length ? (
            <Empty icon={<Clock size={16} />} title="No events yet" detail="Actions performed in the GUI are logged here." />
          ) : (
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Time</th><th>Kind</th><th>Title</th><th>Detail</th></tr></thead>
                <tbody>
                  {events.data.events.map((event) => (
                    <tr key={event.id}>
                      <td className="tiny mono mute">{formatDateTime(Number(event.at) * 1000)}</td>
                      <td><Badge tone={event.level === "warn" ? "warn" : event.level === "error" ? "err" : "dim"}>{titleCase(event.kind)}</Badge></td>
                      <td className="td-strong td-truncate">{event.title}</td>
                      <td className="tiny dim td-truncate" style={{ maxWidth: 420 }}>{event.detail || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
