import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Phase, Run } from "@/lib/types";

const PHASES: Phase[] = ["discover", "triage", "craft", "deliver", "listen", "post", "notify"];

export default function Autonomous() {
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    const { run: next } = await api.post<{ run: Run }>("/autonomous/start", { wifi: true });
    setRun(next);
    setBusy(false);
  };

  useEffect(() => {
    if (!run || ["done", "failed"].includes(run.phase)) return;
    const timer = setInterval(async () => {
      const { run: next } = await api.get<{ run: Run }>(`/autonomous/${run.id}`);
      setRun(next);
    }, 2000);
    return () => clearInterval(timer);
  }, [run?.id, run?.phase]);

  const decide = (decision: string) => run && api.post(`/autonomous/${run.id}/decision`, { decision });
  const active = run ? PHASES.indexOf(run.phase) : -1;

  return (
    <div className="p-6">
      <div className="flex justify-between">
        <h1 className="text-xl font-semibold">Autonomous</h1>
        <button onClick={start} disabled={busy || (!!run && !["done", "failed"].includes(run.phase))}
          className="rounded bg-primary px-4 py-2 text-sm text-accent-contrast disabled:opacity-40">Start</button>
      </div>
      <div className="mt-6 flex gap-1">
        {PHASES.map((p, i) => (
          <div key={p} className={`h-1 flex-1 rounded ${i <= active ? "bg-primary" : "bg-white/10"}`} />
        ))}
      </div>
      {run && (
        <>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {run.targets.map((t) => (
              <div key={t.serial} className="rounded border border-white/10 p-3 text-xs">
                <p className="font-mono">{t.serial}</p>
                <p className="opacity-60">{t.transport} Â· {t.score} Â· {t.vector}</p>
              </div>
            ))}
          </div>
          <pre className="mt-4 h-64 overflow-auto rounded bg-black/40 p-3 font-mono text-xs">
            {run.log.join("\n")}
          </pre>
        </>
      )}
      {run?.phase === "deciding" && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-surface p-6">
            <h2 className="text-lg font-semibold">Cycle complete</h2>
            <div className="mt-5 flex gap-3">
              <button onClick={() => decide("maintain")}
                className="flex-1 rounded bg-success-strong px-4 py-2 text-sm text-white">Maintain</button>
              <button onClick={() => decide("wipe")}
                className="flex-1 rounded bg-danger-strong px-4 py-2 text-sm text-white">Wipe</button>
            </div>
            <button onClick={() => decide("abort")} className="mt-3 text-xs underline opacity-60">Abort</button>
          </div>
        </div>
      )}
    </div>
  );
}
