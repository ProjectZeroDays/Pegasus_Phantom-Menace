import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, useApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Badge, Button, Empty, Modal, Progress, Terminal } from "@/components/ui";
import { formatDateTime, formatMs } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Loader2, XCircle } from "lucide-react";

/** Poll a single job until it reaches a terminal state. */
export function useJob(jobId: string | null, onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const doneRef = useRef(onDone);
  const fired = useRef<string | null>(null);
  doneRef.current = onDone;

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      fired.current = null;
      return;
    }
    let cancelled = false;
    let timer = 0;

    const tick = async () => {
      try {
        const data = await api.get<{ job: Job }>(`/jobs/${jobId}`);
        if (cancelled) return;
        setJob(data.job);
        if (["succeeded", "failed", "cancelled"].includes(data.job.status)) {
          if (fired.current !== jobId) {
            fired.current = jobId;
            doneRef.current?.(data.job);
          }
          return;
        }
      } catch {
        // transient — retry
      }
      timer = window.setTimeout(tick, 900);
    };
    void tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [jobId]);

  return job;
}

/** Global job drawer: list + live output of every dispatched action. */
export function JobDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data, loading, refresh } = useApi<{ jobs: Job[]; stats: Record<string, number> }>(
    "/jobs?limit=25",
    { interval: open ? 2500 : undefined, enabled: open },
  );
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useJob(open ? selected : null);

  useEffect(() => {
    if (open && !selected && data?.jobs?.length) {
      setSelected(data.jobs[0].id);
    }
  }, [open, selected, data]);

  const active = detail ?? data?.jobs.find((j) => j.id === selected) ?? null;

  const cancel = useCallback(async (id: string) => {
    try {
      await api.post(`/jobs/${id}/cancel`);
      refresh();
    } catch {
      /* ignore */
    }
  }, [refresh]);

  if (!open) return null;

  return (
    <Modal
      title="Job activity"
      onClose={onClose}
      width={980}
      footer={
        <>
          <Button size="sm" onClick={refresh} disabled={loading}>
            Refresh
          </Button>
          <Button size="sm" variant="primary" onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 14, minHeight: 380 }}>
        <div className="col" style={{ gap: 6, maxHeight: 460, overflowY: "auto" }}>
          {!data?.jobs?.length && <Empty title="No jobs yet" detail="Run any command to see output here." />}
          {data?.jobs.map((job) => (
            <button
              key={job.id}
              onClick={() => setSelected(job.id)}
              className="cmd-card"
              style={{
                borderColor: selected === job.id ? "rgba(255,61,0,.6)" : undefined,
                gap: 4,
              }}
            >
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="mono tiny strong td-truncate" style={{ maxWidth: 190 }}>
                  {job.title}
                </span>
                <JobBadge status={job.status} />
              </div>
              <div className="tiny mute">
                {job.kind} · {formatDateTime(job.createdAt * 1000)}
              </div>
            </button>
          ))}
        </div>

        <div className="col" style={{ gap: 10 }}>
          {active ? (
            <>
              <div className="row wrap" style={{ justifyContent: "space-between" }}>
                <div className="row" style={{ gap: 8 }}>
                  <JobBadge status={active.status} />
                  <span className="tiny mute">
                    {active.durationMs !== null ? formatMs(active.durationMs) : "running"}
                  </span>
                </div>
                {["queued", "running"].includes(active.status) && (
                  <Button size="xs" variant="danger" onClick={() => void cancel(active.id)}>
                    <XCircle size={12} /> Cancel
                  </Button>
                )}
              </div>
              {active.status === "running" && <Progress value={active.progress * 100} thin />}
              {active.error && (
                <div className="small" style={{ color: "#ff8b95" }}>{active.error}</div>
              )}
              <Terminal
                lines={active.output ?? "(waiting for output…)"}
                title={active.title}
                maxHeight={340}
              />
              {active.result ? (
                <details>
                  <summary className="tiny mute" style={{ cursor: "pointer" }}>
                    structured result
                  </summary>
                  <pre
                    className="tiny"
                    style={{
                      maxHeight: 200,
                      overflow: "auto",
                      background: "#0b0e13",
                      border: "1px solid var(--line-soft)",
                      padding: 10,
                      borderRadius: 6,
                      marginTop: 6,
                    }}
                  >
                    {JSON.stringify(active.result, null, 2)}
                  </pre>
                </details>
              ) : null}
            </>
          ) : (
            <Empty title="Select a job" detail="Choose a job on the left to inspect its output." />
          )}
        </div>
      </div>
    </Modal>
  );
}

function JobBadge({ status }: { status: Job["status"] }) {
  if (status === "running" || status === "queued") {
    return (
      <Badge tone="info">
        <Loader2 size={10} className="spin" /> {status}
      </Badge>
    );
  }
  if (status === "succeeded") return <Badge tone="ok">done</Badge>;
  if (status === "failed") return <Badge tone="err">failed</Badge>;
  return <Badge tone="warn">cancelled</Badge>;
}

/** Compact inline output preview used by feature pages. */
export function JobOutput({
  jobId,
  onDone,
  title,
  height = 260,
}: {
  jobId: string | null;
  onDone?: (job: Job) => void;
  title?: string;
  height?: number;
}) {
  const job = useJob(jobId, onDone);
  const lines = useMemo(() => job?.output ?? "", [job]);
  if (!jobId) return null;
  return (
    <div className="col" style={{ gap: 8 }}>
      <div className="row" style={{ gap: 8 }}>
        <JobBadge status={job?.status ?? "queued"} />
        {job?.durationMs != null && <span className="tiny mute">{formatMs(job.durationMs)}</span>}
        {job?.error && <span className="tiny" style={{ color: "#ff8b95" }}>{job.error}</span>}
        <span className={cn("spacer")} />
        {job && ["queued", "running"].includes(job.status) && (
          <Button size="xs" variant="danger" onClick={() => void api.post(`/jobs/${job.id}/cancel`)}>
            Cancel
          </Button>
        )}
      </div>
      {job?.status === "running" && <Progress value={job.progress * 100} thin />}
      <Terminal
        lines={lines || "(starting…)"}
        title={title ?? job?.title ?? "output"}
        maxHeight={height}
      />
    </div>
  );
}
