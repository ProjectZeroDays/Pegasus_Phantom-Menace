import { useMemo, useState } from "react";
import { Camera, Download, Film, Image as ImageIcon, RefreshCw } from "lucide-react";
import { useTelemetry } from "@/lib/useTelemetry";
import type { PhotoRow, VideoRow } from "@/lib/types";
import { Badge, Button, Empty, Loading, PageHeader, Panel, Segmented, Stat } from "@/components/ui";
import { formatBytes, formatDateTime, formatDuration } from "@/lib/format";

export default function Media() {
  const { data, loading, refresh, collect, serial } = useTelemetry<{
    photos: PhotoRow[];
    videos: VideoRow[];
    collectedAt: number | null;
  }>("media", 90000);
  const [tab, setTab] = useState<"photos" | "videos">("photos");
  const [selected, setSelected] = useState<PhotoRow | null>(null);

  const photos = data?.photos ?? [];
  const videos = data?.videos ?? [];
  const totalBytes = useMemo(
    () => [...photos, ...videos].reduce((acc, row) => acc + row.sizeBytes, 0),
    [photos, videos],
  );

  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
  const src = (url: string) => (url.startsWith("http") ? url : `${apiBase}${url.replace(/^\/api/, "")}`);

  return (
    <div className="page">
      <PageHeader
        title="Photos & Video"
        subtitle="External media store index with live thumbnails"
        actions={
          <>
            <Segmented
              value={tab}
              onChange={setTab}
              options={[
                { value: "photos", label: `Photos (${photos.length})`, icon: <ImageIcon size={12} /> },
                { value: "videos", label: `Videos (${videos.length})`, icon: <Film size={12} /> },
              ]}
            />
            <Button size="sm" onClick={refresh}><RefreshCw size={12} /> Refresh</Button>
            <Button size="sm" variant="primary" onClick={() => void collect()} disabled={!serial}>
              <Camera size={12} /> Index device
            </Button>
          </>
        }
      />

      <div className="stat-grid">
        <Stat value={photos.length} label="Photos indexed" tone="info" />
        <Stat value={videos.length} label="Videos indexed" />
        <Stat value={formatBytes(totalBytes)} label="Media footprint" />
        <Stat value={data?.collectedAt ? formatDateTime(data.collectedAt * 1000) : "—"} label="Last index" />
      </div>

      <Panel title={tab === "photos" ? "Photo library" : "Video library"}>
        {!serial ? (
          <Empty icon={<Camera size={16} />} title="No device selected" detail="Pick a device in the sidebar." />
        ) : loading && !data ? (
          <Loading label="Reading media store…" rows={4} />
        ) : (tab === "photos" ? photos : videos).length === 0 ? (
          <Empty
            icon={tab === "photos" ? <ImageIcon size={16} /> : <Film size={16} />}
            title={`No ${tab} indexed`}
            detail="Index the device to read content://media/external."
            action={<Button size="sm" variant="primary" onClick={() => void collect()}>Index now</Button>}
          />
        ) : (
          <div className="grid-4">
            {(tab === "photos" ? photos : videos).map((row) => (
              <div key={row.id} className="cmd-card" style={{ padding: 0, overflow: "hidden", cursor: "pointer" }} onClick={() => setSelected(row)}>
                <div style={{ position: "relative", aspectRatio: tab === "photos" ? "1 / 1" : "16 / 9", background: "var(--surface-3)" }}>
                  <img
                    src={src(row.thumbnailUrl)}
                    alt={row.name}
                    loading="lazy"
                    style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.9 }}
                    onError={(event) => {
                      (event.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                  {tab === "videos" && (
                    <span className="badge badge-dim" style={{ position: "absolute", right: 6, bottom: 6 }}>
                      {formatDuration((row as VideoRow).durationSeconds)}
                    </span>
                  )}
                </div>
                <div style={{ padding: "8px 10px" }}>
                  <div className="tiny td-truncate strong">{row.name}</div>
                  <div className="row" style={{ justifyContent: "space-between", marginTop: 4 }}>
                    <span className="tiny mute">{formatBytes(row.sizeBytes)}</span>
                    <span className="tiny mute">{row.takenAt ? formatDateTime(row.takenAt) : "—"}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      {selected && (
        <Panel title={selected.name} actions={
          <>
            <Badge tone="dim">{formatBytes(selected.sizeBytes)}</Badge>
            <a className="btn btn-sm" href={src(selected.url)} download>
              <Download size={12} /> Download
            </a>
            <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>close</Button>
          </>
        }>
          <div style={{ display: "grid", placeItems: "center", background: "#06080b", padding: 14, borderRadius: 7 }}>
            <img src={src(selected.url)} alt={selected.name} style={{ maxWidth: "100%", maxHeight: 520, borderRadius: 6 }} />
          </div>
          <div className="kv" style={{ marginTop: 10 }}><span className="kv-k">MIME</span><span className="kv-v mono tiny">{selected.mimeType}</span></div>
          <div className="kv"><span className="kv-k">Taken</span><span className="kv-v tiny">{formatDateTime(selected.takenAt)}</span></div>
        </Panel>
      )}
    </div>
  );
}
