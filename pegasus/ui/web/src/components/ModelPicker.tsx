import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Row { id: string; quant: string; role: string; backend: string; }

export function ModelPicker({ role, onPick }: { role: string; onPick: (id: string) => void }) {
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    api.get<{ models: Row[] }>("/models/recommended")
      .then((d) => setRows(d.models.filter((m) => m.role === role)))
      .catch(() => {});
  }, [role]);

  if (!rows.length) return <p className="text-xs opacity-60">No model for this role on this host.</p>;

  return (
    <ul className="space-y-2">
      {rows.map((m) => (
        <li key={m.id} className="flex items-center justify-between gap-2 rounded border p-2 text-xs">
          <div className="min-w-0">
            <p className="truncate font-mono">{m.id}</p>
            <p className="opacity-60">{m.quant} Â· {m.backend}</p>
          </div>
          <div className="flex gap-1">
            <button onClick={() => api.post("/models/download", { id: m.id, quant: m.quant })}
              className="rounded bg-sky-600 px-2 py-1">Get</button>
            <button onClick={() => onPick(m.id)} className="rounded bg-emerald-600 px-2 py-1">Use</button>
          </div>
        </li>
      ))}
    </ul>
  );
}
